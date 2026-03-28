"""
OASIS 시뮬레이션 러너
백그라운드에서 시뮬레이션을 실행하고 각 Agent의 동작을 기록, 실시간 상태 모니터링 지원
"""

import os
import sys
import json
import time
import asyncio
import threading
import subprocess
import signal
import atexit
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from queue import Queue

from ..config import Config
from ..utils.logger import get_logger
from .zep_graph_memory_updater import ZepGraphMemoryManager
from .simulation_ipc import SimulationIPCClient, CommandType, IPCResponse

logger = get_logger('mirofish.simulation_runner')

# 표시여부이미등록정리함수
_cleanup_registered = False

# 플랫폼감지
IS_WINDOWS = sys.platform == 'win32'


class RunnerStatus(str, Enum):
    """실행기상태"""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentAction:
    """Agent동작기록"""
    round_num: int
    timestamp: str
    platform: str  # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str  # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    success: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "timestamp": self.timestamp,
            "platform": self.platform,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "action_type": self.action_type,
            "action_args": self.action_args,
            "result": self.result,
            "success": self.success,
        }


@dataclass
class RoundSummary:
    """각라운드요약"""
    round_num: int
    start_time: str
    end_time: Optional[str] = None
    simulated_hour: int = 0
    twitter_actions: int = 0
    reddit_actions: int = 0
    active_agents: List[int] = field(default_factory=list)
    actions: List[AgentAction] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "simulated_hour": self.simulated_hour,
            "twitter_actions": self.twitter_actions,
            "reddit_actions": self.reddit_actions,
            "active_agents": self.active_agents,
            "actions_count": len(self.actions),
            "actions": [a.to_dict() for a in self.actions],
        }


@dataclass
class SimulationRunState:
    """시뮬레이션실행상태(실시간)"""
    simulation_id: str
    runner_status: RunnerStatus = RunnerStatus.IDLE
    
    # 진행 상황정보
    current_round: int = 0
    total_rounds: int = 0
    simulated_hours: int = 0
    total_simulation_hours: int = 0
    
    # 각플랫폼독립라운드및시뮬레이션시간(사용되는이중플랫폼병렬표시)
    twitter_current_round: int = 0
    reddit_current_round: int = 0
    twitter_simulated_hours: int = 0
    reddit_simulated_hours: int = 0
    
    # 플랫폼상태
    twitter_running: bool = False
    reddit_running: bool = False
    twitter_actions_count: int = 0
    reddit_actions_count: int = 0
    
    # 플랫폼완료상태(통해감지 actions.jsonl 중의 simulation_end 이벤트)
    twitter_completed: bool = False
    reddit_completed: bool = False
    
    # 각라운드요약
    rounds: List[RoundSummary] = field(default_factory=list)
    
    # 최근동작(사용되는프론트엔드실시간표시)
    recent_actions: List[AgentAction] = field(default_factory=list)
    max_recent_actions: int = 50
    
    # 시간스탬프
    started_at: Optional[str] = None
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    
    # 오류정보
    error: Optional[str] = None
    
    # 프로세스ID(사용되는중지)
    process_pid: Optional[int] = None
    
    def add_action(self, action: AgentAction):
        """추가동작까지최근동작목록"""
        self.recent_actions.insert(0, action)
        if len(self.recent_actions) > self.max_recent_actions:
            self.recent_actions = self.recent_actions[:self.max_recent_actions]
        
        if action.platform == "twitter":
            self.twitter_actions_count += 1
        else:
            self.reddit_actions_count += 1
        
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "runner_status": self.runner_status.value,
            "current_round": self.current_round,
            "total_rounds": self.total_rounds,
            "simulated_hours": self.simulated_hours,
            "total_simulation_hours": self.total_simulation_hours,
            "progress_percent": round(self.current_round / max(self.total_rounds, 1) * 100, 1),
            # 각플랫폼독립라운드및시간
            "twitter_current_round": self.twitter_current_round,
            "reddit_current_round": self.reddit_current_round,
            "twitter_simulated_hours": self.twitter_simulated_hours,
            "reddit_simulated_hours": self.reddit_simulated_hours,
            "twitter_running": self.twitter_running,
            "reddit_running": self.reddit_running,
            "twitter_completed": self.twitter_completed,
            "reddit_completed": self.reddit_completed,
            "twitter_actions_count": self.twitter_actions_count,
            "reddit_actions_count": self.reddit_actions_count,
            "total_actions_count": self.twitter_actions_count + self.reddit_actions_count,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "process_pid": self.process_pid,
        }
    
    def to_detail_dict(self) -> Dict[str, Any]:
        """포함최근동작의상세정보"""
        result = self.to_dict()
        result["recent_actions"] = [a.to_dict() for a in self.recent_actions]
        result["rounds_count"] = len(self.rounds)
        return result


class SimulationRunner:
    """
    시뮬레이션실행기
    
    담당: 
    1. 에서백그라운드프로세스중실행OASIS시뮬레이션
    2. 파싱실행로그, 기록각개Agent의동작
    3. 제공실시간상태조회인터페이스
    4. 지원일시 중지/중지/복구작업
    """
    
    # 실행상태저장디렉토리
    RUN_STATE_DIR = os.path.join(
        os.path.dirname(__file__),
        '../../uploads/simulations'
    )
    
    # 스크립트디렉토리
    SCRIPTS_DIR = os.path.join(
        os.path.dirname(__file__),
        '../../scripts'
    )
    
    # 메모리중의실행상태
    _run_states: Dict[str, SimulationRunState] = {}
    _processes: Dict[str, subprocess.Popen] = {}
    _action_queues: Dict[str, Queue] = {}
    _monitor_threads: Dict[str, threading.Thread] = {}
    _stdout_files: Dict[str, Any] = {}  # 저장 stdout 파일핸들
    _stderr_files: Dict[str, Any] = {}  # 저장 stderr 파일핸들
    
    # 그래프메모리업데이트설정
    _graph_memory_enabled: Dict[str, bool] = {}  # simulation_id -> enabled
    
    @classmethod
    def get_run_state(cls, simulation_id: str) -> Optional[SimulationRunState]:
        """가져오기실행상태"""
        if simulation_id in cls._run_states:
            return cls._run_states[simulation_id]
        
        # 시도에서파일로드
        state = cls._load_run_state(simulation_id)
        if state:
            cls._run_states[simulation_id] = state
        return state
    
    @classmethod
    def _load_run_state(cls, simulation_id: str) -> Optional[SimulationRunState]:
        """에서파일로드실행상태"""
        state_file = os.path.join(cls.RUN_STATE_DIR, simulation_id, "run_state.json")
        if not os.path.exists(state_file):
            return None
        
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            state = SimulationRunState(
                simulation_id=simulation_id,
                runner_status=RunnerStatus(data.get("runner_status", "idle")),
                current_round=data.get("current_round", 0),
                total_rounds=data.get("total_rounds", 0),
                simulated_hours=data.get("simulated_hours", 0),
                total_simulation_hours=data.get("total_simulation_hours", 0),
                # 각플랫폼독립라운드및시간
                twitter_current_round=data.get("twitter_current_round", 0),
                reddit_current_round=data.get("reddit_current_round", 0),
                twitter_simulated_hours=data.get("twitter_simulated_hours", 0),
                reddit_simulated_hours=data.get("reddit_simulated_hours", 0),
                twitter_running=data.get("twitter_running", False),
                reddit_running=data.get("reddit_running", False),
                twitter_completed=data.get("twitter_completed", False),
                reddit_completed=data.get("reddit_completed", False),
                twitter_actions_count=data.get("twitter_actions_count", 0),
                reddit_actions_count=data.get("reddit_actions_count", 0),
                started_at=data.get("started_at"),
                updated_at=data.get("updated_at", datetime.now().isoformat()),
                completed_at=data.get("completed_at"),
                error=data.get("error"),
                process_pid=data.get("process_pid"),
            )
            
            # 로드최근동작
            actions_data = data.get("recent_actions", [])
            for a in actions_data:
                state.recent_actions.append(AgentAction(
                    round_num=a.get("round_num", 0),
                    timestamp=a.get("timestamp", ""),
                    platform=a.get("platform", ""),
                    agent_id=a.get("agent_id", 0),
                    agent_name=a.get("agent_name", ""),
                    action_type=a.get("action_type", ""),
                    action_args=a.get("action_args", {}),
                    result=a.get("result"),
                    success=a.get("success", True),
                ))
            
            return state
        except Exception as e:
            logger.error(f"로드실행상태실패: {str(e)}")
            return None
    
    @classmethod
    def _save_run_state(cls, state: SimulationRunState):
        """저장실행상태까지파일"""
        sim_dir = os.path.join(cls.RUN_STATE_DIR, state.simulation_id)
        os.makedirs(sim_dir, exist_ok=True)
        state_file = os.path.join(sim_dir, "run_state.json")
        
        data = state.to_detail_dict()
        
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        cls._run_states[state.simulation_id] = state
    
    @classmethod
    def start_simulation(
        cls,
        simulation_id: str,
        platform: str = "parallel",  # twitter / reddit / parallel
        max_rounds: int = None,  # 최대시뮬레이션라운드 수(선택, 사용되는잘림과도하게 긴의시뮬레이션)
        enable_graph_memory_update: bool = False,  # 여부을활동업데이트까지Zep그래프
        graph_id: str = None  # Zep그래프ID(활성화그래프업데이트시필수)
    ) -> SimulationRunState:
        """
        시작시뮬레이션
        
        Args:
            simulation_id: 시뮬레이션ID
            platform: 실행플랫폼 (twitter/reddit/parallel)
            max_rounds: 최대시뮬레이션라운드 수(선택, 사용되는잘림과도하게 긴의시뮬레이션)
            enable_graph_memory_update: 여부을Agent활동동적업데이트까지Zep그래프
            graph_id: Zep그래프ID(활성화그래프업데이트시필수)
            
        Returns:
            SimulationRunState
        """
        # 확인여부이미에서실행
        existing = cls.get_run_state(simulation_id)
        if existing and existing.runner_status in [RunnerStatus.RUNNING, RunnerStatus.STARTING]:
            raise ValueError(f"시뮬레이션이미에서실행중: {simulation_id}")
        
        # 로드시뮬레이션설정
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        if not os.path.exists(config_path):
            raise ValueError(f"시뮬레이션설정존재하지 않음, 먼저 호출 /prepare 인터페이스")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 초기화실행상태
        time_config = config.get("time_config", {})
        total_hours = time_config.get("total_simulation_hours", 72)
        minutes_per_round = time_config.get("minutes_per_round", 30)
        total_rounds = int(total_hours * 60 / minutes_per_round)
        
        # 만약지정함최대라운드 수, 따라서잘림
        if max_rounds is not None and max_rounds > 0:
            original_rounds = total_rounds
            total_rounds = min(total_rounds, max_rounds)
            if total_rounds < original_rounds:
                logger.info(f"라운드 수이미잘림: {original_rounds} -> {total_rounds} (max_rounds={max_rounds})")
        
        state = SimulationRunState(
            simulation_id=simulation_id,
            runner_status=RunnerStatus.STARTING,
            total_rounds=total_rounds,
            total_simulation_hours=total_hours,
            started_at=datetime.now().isoformat(),
        )
        
        cls._save_run_state(state)
        
        # 만약활성화그래프메모리업데이트, 생성업데이트기
        if enable_graph_memory_update:
            if not graph_id:
                raise ValueError("활성화그래프메모리업데이트시필수제공 graph_id")
            
            try:
                ZepGraphMemoryManager.create_updater(simulation_id, graph_id)
                cls._graph_memory_enabled[simulation_id] = True
                logger.info(f"이미활성화그래프메모리업데이트: simulation_id={simulation_id}, graph_id={graph_id}")
            except Exception as e:
                logger.error(f"생성그래프메모리업데이트기실패: {e}")
                cls._graph_memory_enabled[simulation_id] = False
        else:
            cls._graph_memory_enabled[simulation_id] = False
        
        # 확정실행어떤개스크립트(스크립트위치한 backend/scripts/ 디렉토리)
        if platform == "twitter":
            script_name = "run_twitter_simulation.py"
            state.twitter_running = True
        elif platform == "reddit":
            script_name = "run_reddit_simulation.py"
            state.reddit_running = True
        else:
            script_name = "run_parallel_simulation.py"
            state.twitter_running = True
            state.reddit_running = True
        
        script_path = os.path.join(cls.SCRIPTS_DIR, script_name)
        
        if not os.path.exists(script_path):
            raise ValueError(f"스크립트존재하지 않음: {script_path}")
        
        # 생성동작큐
        action_queue = Queue()
        cls._action_queues[simulation_id] = action_queue
        
        # 시작시뮬레이션프로세스
        try:
            # 구축실행명령, 사용완전한경로
            # 새의로그구조: 
            #   twitter/actions.jsonl - Twitter 동작로그
            #   reddit/actions.jsonl  - Reddit 동작로그
            #   simulation.log        - 주프로세스로그
            
            cmd = [
                sys.executable,  # Python인터프리터
                script_path,
                "--config", config_path,  # 사용완전한설정파일경로
            ]
            
            # 만약지정함최대라운드 수, 추가까지명령행파라미터
            if max_rounds is not None and max_rounds > 0:
                cmd.extend(["--max-rounds", str(max_rounds)])
            
            # 생성주로그파일, 방지 stdout/stderr 파이프버퍼가득 차초래하여프로세스차단
            main_log_path = os.path.join(sim_dir, "simulation.log")
            main_log_file = open(main_log_path, 'w', encoding='utf-8')
            
            # 설정하위 프로세스환경변수, 보장 Windows 상사용 UTF-8 인코딩
            # 이것가능수정제드식라이브러리(예 OASIS)읽기파일시미지정인코딩의질문
            env = os.environ.copy()
            env['PYTHONUTF8'] = '1'  # Python 3.7+ 지원, 하여모든 open() 기본사용 UTF-8
            env['PYTHONIOENCODING'] = 'utf-8'  # 보장 stdout/stderr 사용 UTF-8
            
            # 설정작업디렉토리를시뮬레이션디렉토리(데이터라이브러리등파일회생성에서이)
            # 사용 start_new_session=True 생성새의프로세스그룹, 보장가능통해 os.killpg 종료모든하위 프로세스
            process = subprocess.Popen(
                cmd,
                cwd=sim_dir,
                stdout=main_log_file,
                stderr=subprocess.STDOUT,  # stderr 또한쓰기동일한개파일
                text=True,
                encoding='utf-8',  # 명시적으로지정인코딩
                bufsize=1,
                env=env,  # 전달포함있음 UTF-8 설정의환경변수
                start_new_session=True,  # 생성새프로세스그룹, 보장서버종료시수종료모든관련프로세스
            )
            
            # 저장파일핸들위해후속종료
            cls._stdout_files[simulation_id] = main_log_file
            cls._stderr_files[simulation_id] = None  # 않다시필요별도의 stderr
            
            state.process_pid = process.pid
            state.runner_status = RunnerStatus.RUNNING
            cls._processes[simulation_id] = process
            cls._save_run_state(state)
            
            # 시작모니터링스레드
            monitor_thread = threading.Thread(
                target=cls._monitor_simulation,
                args=(simulation_id,),
                daemon=True
            )
            monitor_thread.start()
            cls._monitor_threads[simulation_id] = monitor_thread
            
            logger.info(f"시뮬레이션시작성공: {simulation_id}, pid={process.pid}, platform={platform}")
            
        except Exception as e:
            state.runner_status = RunnerStatus.FAILED
            state.error = str(e)
            cls._save_run_state(state)
            raise
        
        return state
    
    @classmethod
    def _monitor_simulation(cls, simulation_id: str):
        """모니터링시뮬레이션프로세스, 파싱동작로그"""
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        
        # 새의로그구조: 분플랫폼의동작로그
        twitter_actions_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        reddit_actions_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        
        process = cls._processes.get(simulation_id)
        state = cls.get_run_state(simulation_id)
        
        if not process or not state:
            return
        
        twitter_position = 0
        reddit_position = 0
        
        try:
            while process.poll() is None:  # 프로세스여전히에서실행
                # 읽기 Twitter 동작로그
                if os.path.exists(twitter_actions_log):
                    twitter_position = cls._read_action_log(
                        twitter_actions_log, twitter_position, state, "twitter"
                    )
                
                # 읽기 Reddit 동작로그
                if os.path.exists(reddit_actions_log):
                    reddit_position = cls._read_action_log(
                        reddit_actions_log, reddit_position, state, "reddit"
                    )
                
                # 업데이트상태
                cls._save_run_state(state)
                time.sleep(2)
            
            # 프로세스종료후, 가장후읽기한 번로그
            if os.path.exists(twitter_actions_log):
                cls._read_action_log(twitter_actions_log, twitter_position, state, "twitter")
            if os.path.exists(reddit_actions_log):
                cls._read_action_log(reddit_actions_log, reddit_position, state, "reddit")
            
            # 프로세스종료
            exit_code = process.returncode
            
            if exit_code == 0:
                state.runner_status = RunnerStatus.COMPLETED
                state.completed_at = datetime.now().isoformat()
                logger.info(f"시뮬레이션완료: {simulation_id}")
            else:
                state.runner_status = RunnerStatus.FAILED
                # 에서주로그파일읽기오류정보
                main_log_path = os.path.join(sim_dir, "simulation.log")
                error_info = ""
                try:
                    if os.path.exists(main_log_path):
                        with open(main_log_path, 'r', encoding='utf-8') as f:
                            error_info = f.read()[-2000:]  # 취가장후2000문자
                except Exception:
                    pass
                state.error = f"프로세스종료 코드: {exit_code}, 오류: {error_info}"
                logger.error(f"시뮬레이션실패: {simulation_id}, error={state.error}")
            
            state.twitter_running = False
            state.reddit_running = False
            cls._save_run_state(state)
            
        except Exception as e:
            logger.error(f"모니터링스레드예외: {simulation_id}, error={str(e)}")
            state.runner_status = RunnerStatus.FAILED
            state.error = str(e)
            cls._save_run_state(state)
        
        finally:
            # 중지그래프메모리업데이트기
            if cls._graph_memory_enabled.get(simulation_id, False):
                try:
                    ZepGraphMemoryManager.stop_updater(simulation_id)
                    logger.info(f"이미중지그래프메모리업데이트: simulation_id={simulation_id}")
                except Exception as e:
                    logger.error(f"중지그래프메모리업데이트기실패: {e}")
                cls._graph_memory_enabled.pop(simulation_id, None)
            
            # 정리프로세스리소스
            cls._processes.pop(simulation_id, None)
            cls._action_queues.pop(simulation_id, None)
            
            # 종료로그파일핸들
            if simulation_id in cls._stdout_files:
                try:
                    cls._stdout_files[simulation_id].close()
                except Exception:
                    pass
                cls._stdout_files.pop(simulation_id, None)
            if simulation_id in cls._stderr_files and cls._stderr_files[simulation_id]:
                try:
                    cls._stderr_files[simulation_id].close()
                except Exception:
                    pass
                cls._stderr_files.pop(simulation_id, None)
    
    @classmethod
    def _read_action_log(
        cls, 
        log_path: str, 
        position: int, 
        state: SimulationRunState,
        platform: str
    ) -> int:
        """
        읽기동작로그파일
        
        Args:
            log_path: 로그파일경로
            position: 상회읽기위치
            state: 실행상태객체
            platform: 플랫폼이름 (twitter/reddit)
            
        Returns:
            새의읽기위치
        """
        # 확인여부활성화함그래프메모리업데이트
        graph_memory_enabled = cls._graph_memory_enabled.get(state.simulation_id, False)
        graph_updater = None
        if graph_memory_enabled:
            graph_updater = ZepGraphMemoryManager.get_updater(state.simulation_id)
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                f.seek(position)
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            action_data = json.loads(line)
                            
                            # 처리이벤트유형의조건목
                            if "event_type" in action_data:
                                event_type = action_data.get("event_type")
                                
                                # 감지 simulation_end 이벤트, 표시플랫폼이미완료
                                if event_type == "simulation_end":
                                    if platform == "twitter":
                                        state.twitter_completed = True
                                        state.twitter_running = False
                                        logger.info(f"Twitter 시뮬레이션이미완료: {state.simulation_id}, total_rounds={action_data.get('total_rounds')}, total_actions={action_data.get('total_actions')}")
                                    elif platform == "reddit":
                                        state.reddit_completed = True
                                        state.reddit_running = False
                                        logger.info(f"Reddit 시뮬레이션이미완료: {state.simulation_id}, total_rounds={action_data.get('total_rounds')}, total_actions={action_data.get('total_actions')}")
                                    
                                    # 확인여부모든활성화의플랫폼모두이미완료
                                    # 만약만실행함일개플랫폼, 만확인그개플랫폼
                                    # 만약실행함2개플랫폼, 필요2개모두완료
                                    all_completed = cls._check_all_platforms_completed(state)
                                    if all_completed:
                                        state.runner_status = RunnerStatus.COMPLETED
                                        state.completed_at = datetime.now().isoformat()
                                        logger.info(f"모든플랫폼시뮬레이션이미완료: {state.simulation_id}")
                                
                                # 업데이트라운드정보(에서 round_end 이벤트)
                                elif event_type == "round_end":
                                    round_num = action_data.get("round", 0)
                                    simulated_hours = action_data.get("simulated_hours", 0)
                                    
                                    # 업데이트각플랫폼독립의라운드및시간
                                    if platform == "twitter":
                                        if round_num > state.twitter_current_round:
                                            state.twitter_current_round = round_num
                                        state.twitter_simulated_hours = simulated_hours
                                    elif platform == "reddit":
                                        if round_num > state.reddit_current_round:
                                            state.reddit_current_round = round_num
                                        state.reddit_simulated_hours = simulated_hours
                                    
                                    # 전체라운드취2개플랫폼의최대값
                                    if round_num > state.current_round:
                                        state.current_round = round_num
                                    # 전체시간취2개플랫폼의최대값
                                    state.simulated_hours = max(state.twitter_simulated_hours, state.reddit_simulated_hours)
                                
                                continue
                            
                            action = AgentAction(
                                round_num=action_data.get("round", 0),
                                timestamp=action_data.get("timestamp", datetime.now().isoformat()),
                                platform=platform,
                                agent_id=action_data.get("agent_id", 0),
                                agent_name=action_data.get("agent_name", ""),
                                action_type=action_data.get("action_type", ""),
                                action_args=action_data.get("action_args", {}),
                                result=action_data.get("result"),
                                success=action_data.get("success", True),
                            )
                            state.add_action(action)
                            
                            # 업데이트라운드
                            if action.round_num and action.round_num > state.current_round:
                                state.current_round = action.round_num
                            
                            # 만약활성화함그래프메모리업데이트, 을활동전송까지Zep
                            if graph_updater:
                                graph_updater.add_activity_from_dict(action_data, platform)
                            
                        except json.JSONDecodeError:
                            pass
                return f.tell()
        except Exception as e:
            logger.warning(f"읽기동작로그실패: {log_path}, error={e}")
            return position
    
    @classmethod
    def _check_all_platforms_completed(cls, state: SimulationRunState) -> bool:
        """
        확인모든활성화의플랫폼여부모두이미완료시뮬레이션
        
        통해확인해당의 actions.jsonl 파일여부존에서오판단플랫폼여부된활성화
        
        Returns:
            True 만약모든활성화의플랫폼모두이미완료
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, state.simulation_id)
        twitter_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        reddit_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        
        # 확인어떤플랫폼된활성화(통해파일여부존에서판단)
        twitter_enabled = os.path.exists(twitter_log)
        reddit_enabled = os.path.exists(reddit_log)
        
        # 만약플랫폼된활성화하지만미완료, 따라서반환 False
        if twitter_enabled and not state.twitter_completed:
            return False
        if reddit_enabled and not state.reddit_completed:
            return False
        
        # 최소있음일개플랫폼된활성화이고이미완료
        return twitter_enabled or reddit_enabled
    
    @classmethod
    def _terminate_process(cls, process: subprocess.Popen, simulation_id: str, timeout: int = 10):
        """
        크로스플랫폼종료프로세스및 그하위 프로세스
        
        Args:
            process: 요종료의프로세스
            simulation_id: 시뮬레이션ID(사용되는로그)
            timeout: 대기프로세스종료의타임아웃시간(초)
        """
        if IS_WINDOWS:
            # Windows: 사용 taskkill 명령종료프로세스트리
            # /F = 강제종료, /T = 종료프로세스트리(포함하위 프로세스)
            logger.info(f"종료프로세스트리 (Windows): simulation={simulation_id}, pid={process.pid}")
            try:
                # 먼저 시도최아한종료
                subprocess.run(
                    ['taskkill', '/PID', str(process.pid), '/T'],
                    capture_output=True,
                    timeout=5
                )
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # 강제종료
                    logger.warning(f"프로세스미응답, 강제종료: {simulation_id}")
                    subprocess.run(
                        ['taskkill', '/F', '/PID', str(process.pid), '/T'],
                        capture_output=True,
                        timeout=5
                    )
                    process.wait(timeout=5)
            except Exception as e:
                logger.warning(f"taskkill 실패, 시도 terminate: {e}")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        else:
            # Unix: 사용프로세스그룹종료
            # 유치사용함 start_new_session=True, 프로세스그룹 ID 등치주프로세스 PID
            pgid = os.getpgid(process.pid)
            logger.info(f"종료프로세스그룹 (Unix): simulation={simulation_id}, pgid={pgid}")
            
            # 먼저 전송 SIGTERM 에게정개프로세스그룹
            os.killpg(pgid, signal.SIGTERM)
            
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # 만약타임아웃후아직없종료, 강제전송 SIGKILL
                logger.warning(f"프로세스그룹미응답 SIGTERM, 강제종료: {simulation_id}")
                os.killpg(pgid, signal.SIGKILL)
                process.wait(timeout=5)
    
    @classmethod
    def stop_simulation(cls, simulation_id: str) -> SimulationRunState:
        """중지시뮬레이션"""
        state = cls.get_run_state(simulation_id)
        if not state:
            raise ValueError(f"시뮬레이션존재하지 않음: {simulation_id}")
        
        if state.runner_status not in [RunnerStatus.RUNNING, RunnerStatus.PAUSED]:
            raise ValueError(f"시뮬레이션미에서실행: {simulation_id}, status={state.runner_status}")
        
        state.runner_status = RunnerStatus.STOPPING
        cls._save_run_state(state)
        
        # 종료프로세스
        process = cls._processes.get(simulation_id)
        if process and process.poll() is None:
            try:
                cls._terminate_process(process, simulation_id)
            except ProcessLookupError:
                # 프로세스이미경존재하지 않음
                pass
            except Exception as e:
                logger.error(f"종료프로세스그룹실패: {simulation_id}, error={e}")
                # 폴백까지직접종료프로세스
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    process.kill()
        
        state.runner_status = RunnerStatus.STOPPED
        state.twitter_running = False
        state.reddit_running = False
        state.completed_at = datetime.now().isoformat()
        cls._save_run_state(state)
        
        # 중지그래프메모리업데이트기
        if cls._graph_memory_enabled.get(simulation_id, False):
            try:
                ZepGraphMemoryManager.stop_updater(simulation_id)
                logger.info(f"이미중지그래프메모리업데이트: simulation_id={simulation_id}")
            except Exception as e:
                logger.error(f"중지그래프메모리업데이트기실패: {e}")
            cls._graph_memory_enabled.pop(simulation_id, None)
        
        logger.info(f"시뮬레이션이미중지: {simulation_id}")
        return state
    
    @classmethod
    def _read_actions_from_file(
        cls,
        file_path: str,
        default_platform: Optional[str] = None,
        platform_filter: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
        에서단개동작파일중읽기동작
        
        Args:
            file_path: 동작로그파일경로
            default_platform: 기본플랫폼(당동작기록중없있음 platform 필드시사용)
            platform_filter: 필터링플랫폼
            agent_id: 필터링 Agent ID
            round_num: 필터링라운드
        """
        if not os.path.exists(file_path):
            return []
        
        actions = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    
                    # 조건너뛰기비동작기록(예 simulation_start, round_start, round_end 등이벤트)
                    if "event_type" in data:
                        continue
                    
                    # 조건너뛰기없있음 agent_id 의기록(비 Agent 동작)
                    if "agent_id" not in data:
                        continue
                    
                    # 가져오기플랫폼: 우선 사용기록중의 platform, 그렇지 않으면사용기본플랫폼
                    record_platform = data.get("platform") or default_platform or ""
                    
                    # 필터링
                    if platform_filter and record_platform != platform_filter:
                        continue
                    if agent_id is not None and data.get("agent_id") != agent_id:
                        continue
                    if round_num is not None and data.get("round") != round_num:
                        continue
                    
                    actions.append(AgentAction(
                        round_num=data.get("round", 0),
                        timestamp=data.get("timestamp", ""),
                        platform=record_platform,
                        agent_id=data.get("agent_id", 0),
                        agent_name=data.get("agent_name", ""),
                        action_type=data.get("action_type", ""),
                        action_args=data.get("action_args", {}),
                        result=data.get("result"),
                        success=data.get("success", True),
                    ))
                    
                except json.JSONDecodeError:
                    continue
        
        return actions
    
    @classmethod
    def get_all_actions(
        cls,
        simulation_id: str,
        platform: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
        가져오기모든플랫폼의완전한동작이력(없음페이지네이션제한)
        
        Args:
            simulation_id: 시뮬레이션ID
            platform: 필터링플랫폼(twitter/reddit)
            agent_id: 필터링Agent
            round_num: 필터링라운드
            
        Returns:
            완전한의동작목록(시간순스탬프정렬, 새의에서앞)
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        actions = []
        
        # 읽기 Twitter 동작파일(에 따라파일경로자동설정 platform 를 twitter)
        twitter_actions_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        if not platform or platform == "twitter":
            actions.extend(cls._read_actions_from_file(
                twitter_actions_log,
                default_platform="twitter",  # 자동채우기 platform 필드
                platform_filter=platform,
                agent_id=agent_id, 
                round_num=round_num
            ))
        
        # 읽기 Reddit 동작파일(에 따라파일경로자동설정 platform 를 reddit)
        reddit_actions_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        if not platform or platform == "reddit":
            actions.extend(cls._read_actions_from_file(
                reddit_actions_log,
                default_platform="reddit",  # 자동채우기 platform 필드
                platform_filter=platform,
                agent_id=agent_id,
                round_num=round_num
            ))
        
        # 만약분플랫폼파일존재하지 않음, 시도읽기기존의단일파일형식
        if not actions:
            actions_log = os.path.join(sim_dir, "actions.jsonl")
            actions = cls._read_actions_from_file(
                actions_log,
                default_platform=None,  # 기존 형식파일중응해당있음 platform 필드
                platform_filter=platform,
                agent_id=agent_id,
                round_num=round_num
            )
        
        # 시간순스탬프정렬(새의에서앞)
        actions.sort(key=lambda x: x.timestamp, reverse=True)
        
        return actions
    
    @classmethod
    def get_actions(
        cls,
        simulation_id: str,
        limit: int = 100,
        offset: int = 0,
        platform: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
        가져오기동작이력(포함페이지네이션)
        
        Args:
            simulation_id: 시뮬레이션ID
            limit: 반환수량제한
            offset: 오프셋
            platform: 필터링플랫폼
            agent_id: 필터링Agent
            round_num: 필터링라운드
            
        Returns:
            동작목록
        """
        actions = cls.get_all_actions(
            simulation_id=simulation_id,
            platform=platform,
            agent_id=agent_id,
            round_num=round_num
        )
        
        # 페이지네이션
        return actions[offset:offset + limit]
    
    @classmethod
    def get_timeline(
        cls,
        simulation_id: str,
        start_round: int = 0,
        end_round: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        가져오기시뮬레이션시간선(라운드별집계)
        
        Args:
            simulation_id: 시뮬레이션ID
            start_round: 시작라운드
            end_round: 종료라운드
            
        Returns:
            각라운드의집계정보
        """
        actions = cls.get_actions(simulation_id, limit=10000)
        
        # 라운드별그룹화
        rounds: Dict[int, Dict[str, Any]] = {}
        
        for action in actions:
            round_num = action.round_num
            
            if round_num < start_round:
                continue
            if end_round is not None and round_num > end_round:
                continue
            
            if round_num not in rounds:
                rounds[round_num] = {
                    "round_num": round_num,
                    "twitter_actions": 0,
                    "reddit_actions": 0,
                    "active_agents": set(),
                    "action_types": {},
                    "first_action_time": action.timestamp,
                    "last_action_time": action.timestamp,
                }
            
            r = rounds[round_num]
            
            if action.platform == "twitter":
                r["twitter_actions"] += 1
            else:
                r["reddit_actions"] += 1
            
            r["active_agents"].add(action.agent_id)
            r["action_types"][action.action_type] = r["action_types"].get(action.action_type, 0) + 1
            r["last_action_time"] = action.timestamp
        
        # 변환를목록
        result = []
        for round_num in sorted(rounds.keys()):
            r = rounds[round_num]
            result.append({
                "round_num": round_num,
                "twitter_actions": r["twitter_actions"],
                "reddit_actions": r["reddit_actions"],
                "total_actions": r["twitter_actions"] + r["reddit_actions"],
                "active_agents_count": len(r["active_agents"]),
                "active_agents": list(r["active_agents"]),
                "action_types": r["action_types"],
                "first_action_time": r["first_action_time"],
                "last_action_time": r["last_action_time"],
            })
        
        return result
    
    @classmethod
    def get_agent_stats(cls, simulation_id: str) -> List[Dict[str, Any]]:
        """
        각Agent의통계정보
        
        Returns:
            Agent통계목록
        """
        actions = cls.get_actions(simulation_id, limit=10000)
        
        agent_stats: Dict[int, Dict[str, Any]] = {}
        
        for action in actions:
            agent_id = action.agent_id
            
            if agent_id not in agent_stats:
                agent_stats[agent_id] = {
                    "agent_id": agent_id,
                    "agent_name": action.agent_name,
                    "total_actions": 0,
                    "twitter_actions": 0,
                    "reddit_actions": 0,
                    "action_types": {},
                    "first_action_time": action.timestamp,
                    "last_action_time": action.timestamp,
                }
            
            stats = agent_stats[agent_id]
            stats["total_actions"] += 1
            
            if action.platform == "twitter":
                stats["twitter_actions"] += 1
            else:
                stats["reddit_actions"] += 1
            
            stats["action_types"][action.action_type] = stats["action_types"].get(action.action_type, 0) + 1
            stats["last_action_time"] = action.timestamp
        
        # 총동작수정렬
        result = sorted(agent_stats.values(), key=lambda x: x["total_actions"], reverse=True)
        
        return result
    
    @classmethod
    def cleanup_simulation_logs(cls, simulation_id: str) -> Dict[str, Any]:
        """
        정리시뮬레이션의실행로그(사용되는강제중새시작시뮬레이션)
        
        회삭제이하파일: 
        - run_state.json
        - twitter/actions.jsonl
        - reddit/actions.jsonl
        - simulation.log
        - stdout.log / stderr.log
        - twitter_simulation.db(시뮬레이션데이터라이브러리)
        - reddit_simulation.db(시뮬레이션데이터라이브러리)
        - env_status.json(환경상태)
        
        주의: 않회삭제설정파일(simulation_config.json)및 profile 파일
        
        Args:
            simulation_id: 시뮬레이션ID
            
        Returns:
            정리결과정보
        """
        import shutil
        
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        
        if not os.path.exists(sim_dir):
            return {"success": True, "message": "시뮬레이션디렉토리존재하지 않음, 없음필요정리"}
        
        cleaned_files = []
        errors = []
        
        # 요삭제의파일목록(포함데이터라이브러리파일)
        files_to_delete = [
            "run_state.json",
            "simulation.log",
            "stdout.log",
            "stderr.log",
            "twitter_simulation.db",  # Twitter 플랫폼데이터라이브러리
            "reddit_simulation.db",   # Reddit 플랫폼데이터라이브러리
            "env_status.json",        # 환경상태파일
        ]
        
        # 요삭제의디렉토리목록(포함동작로그)
        dirs_to_clean = ["twitter", "reddit"]
        
        # 삭제파일
        for filename in files_to_delete:
            file_path = os.path.join(sim_dir, filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    cleaned_files.append(filename)
                except Exception as e:
                    errors.append(f"삭제 {filename} 실패: {str(e)}")
        
        # 정리플랫폼디렉토리중의동작로그
        for dir_name in dirs_to_clean:
            dir_path = os.path.join(sim_dir, dir_name)
            if os.path.exists(dir_path):
                actions_file = os.path.join(dir_path, "actions.jsonl")
                if os.path.exists(actions_file):
                    try:
                        os.remove(actions_file)
                        cleaned_files.append(f"{dir_name}/actions.jsonl")
                    except Exception as e:
                        errors.append(f"삭제 {dir_name}/actions.jsonl 실패: {str(e)}")
        
        # 정리메모리중의실행상태
        if simulation_id in cls._run_states:
            del cls._run_states[simulation_id]
        
        logger.info(f"정리시뮬레이션로그완료: {simulation_id}, 삭제파일: {cleaned_files}")
        
        return {
            "success": len(errors) == 0,
            "cleaned_files": cleaned_files,
            "errors": errors if errors else None
        }
    
    # 방지중복정리의플래그
    _cleanup_done = False
    
    @classmethod
    def cleanup_all_simulations(cls):
        """
        정리모든실행중의시뮬레이션프로세스
        
        에서서버종료시호출, 보장모든하위 프로세스된종료
        """
        # 방지중복정리
        if cls._cleanup_done:
            return
        cls._cleanup_done = True
        
        # 확인여부있음내용필요정리(방지빈 프로세스의프로세스출력없음사용로그)
        has_processes = bool(cls._processes)
        has_updaters = bool(cls._graph_memory_enabled)
        
        if not has_processes and not has_updaters:
            return  # 없있음필요정리의내용, 조용히반환
        
        logger.info("진행 중정리모든시뮬레이션프로세스...")
        
        # 먼저중지모든그래프메모리업데이트기(stop_all 내부회출력로그)
        try:
            ZepGraphMemoryManager.stop_all()
        except Exception as e:
            logger.error(f"중지그래프메모리업데이트기실패: {e}")
        cls._graph_memory_enabled.clear()
        
        # 복사딕셔너리이방지에서반복시수정
        processes = list(cls._processes.items())
        
        for simulation_id, process in processes:
            try:
                if process.poll() is None:  # 프로세스여전히에서실행
                    logger.info(f"종료시뮬레이션프로세스: {simulation_id}, pid={process.pid}")
                    
                    try:
                        # 사용크로스플랫폼의프로세스종료메서드
                        cls._terminate_process(process, simulation_id, timeout=5)
                    except (ProcessLookupError, OSError):
                        # 프로세스가수이미경존재하지 않음, 시도직접종료
                        try:
                            process.terminate()
                            process.wait(timeout=3)
                        except Exception:
                            process.kill()
                    
                    # 업데이트 run_state.json
                    state = cls.get_run_state(simulation_id)
                    if state:
                        state.runner_status = RunnerStatus.STOPPED
                        state.twitter_running = False
                        state.reddit_running = False
                        state.completed_at = datetime.now().isoformat()
                        state.error = "서버종료, 시뮬레이션된종료"
                        cls._save_run_state(state)
                    
                    # 동시업데이트 state.json, 을상태설를 stopped
                    try:
                        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
                        state_file = os.path.join(sim_dir, "state.json")
                        logger.info(f"시도업데이트 state.json: {state_file}")
                        if os.path.exists(state_file):
                            with open(state_file, 'r', encoding='utf-8') as f:
                                state_data = json.load(f)
                            state_data['status'] = 'stopped'
                            state_data['updated_at'] = datetime.now().isoformat()
                            with open(state_file, 'w', encoding='utf-8') as f:
                                json.dump(state_data, f, indent=2, ensure_ascii=False)
                            logger.info(f"이미업데이트 state.json 상태를 stopped: {simulation_id}")
                        else:
                            logger.warning(f"state.json 존재하지 않음: {state_file}")
                    except Exception as state_err:
                        logger.warning(f"업데이트 state.json 실패: {simulation_id}, error={state_err}")
                        
            except Exception as e:
                logger.error(f"정리프로세스실패: {simulation_id}, error={e}")
        
        # 정리파일핸들
        for simulation_id, file_handle in list(cls._stdout_files.items()):
            try:
                if file_handle:
                    file_handle.close()
            except Exception:
                pass
        cls._stdout_files.clear()
        
        for simulation_id, file_handle in list(cls._stderr_files.items()):
            try:
                if file_handle:
                    file_handle.close()
            except Exception:
                pass
        cls._stderr_files.clear()
        
        # 정리메모리중의상태
        cls._processes.clear()
        cls._action_queues.clear()
        
        logger.info("시뮬레이션프로세스정리완료")
    
    @classmethod
    def register_cleanup(cls):
        """
        등록정리함수
        
        에서 Flask 응사용시작시호출, 보장서버종료시정리모든시뮬레이션프로세스
        """
        global _cleanup_registered
        
        if _cleanup_registered:
            return
        
        # Flask debug 모드하, 만에서 reloader 하위 프로세스중등록정리(실제실행응사용의프로세스)
        # WERKZEUG_RUN_MAIN=true 표시임 reloader 하위 프로세스
        # 만약않임 debug 모드, 따라서없있음이환경변수, 또한필요등록
        is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
        is_debug_mode = os.environ.get('FLASK_DEBUG') == '1' or os.environ.get('WERKZEUG_RUN_MAIN') is not None
        
        # 에서 debug 모드하, 만에서 reloader 하위 프로세스중등록；비 debug 모드하항목상등록
        if is_debug_mode and not is_reloader_process:
            _cleanup_registered = True  # 표시이미등록, 방지하위 프로세스다시회시도
            return
        
        # 저장원래의시그널처리기
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)
        # SIGHUP 만에서 Unix 시스템존에서(macOS/Linux), Windows 없있음
        original_sighup = None
        has_sighup = hasattr(signal, 'SIGHUP')
        if has_sighup:
            original_sighup = signal.getsignal(signal.SIGHUP)
        
        def cleanup_handler(signum=None, frame=None):
            """시그널처리기: 먼저 정리시뮬레이션프로세스, 다시호출원래 처리기"""
            # 만있음에서있음프로세스필요정리시할출력로그
            if cls._processes or cls._graph_memory_enabled:
                logger.info(f"수신한시그널 {signum}, 시작정리...")
            cls.cleanup_all_simulations()
            
            # 호출원래의시그널처리기, 하여 Flask 정상 종료
            if signum == signal.SIGINT and callable(original_sigint):
                original_sigint(signum, frame)
            elif signum == signal.SIGTERM and callable(original_sigterm):
                original_sigterm(signum, frame)
            elif has_sighup and signum == signal.SIGHUP:
                # SIGHUP: 터미널종료 시 전송
                if callable(original_sighup):
                    original_sighup(signum, frame)
                else:
                    # 기본행를: 정상 종료
                    sys.exit(0)
            else:
                # 만약원래 처리기않가호출(예 SIG_DFL), 따라서사용기본행를
                raise KeyboardInterrupt
        
        # 등록 atexit 처리기(으로를백업)
        atexit.register(cls.cleanup_all_simulations)
        
        # 등록시그널처리기(만에서주스레드중)
        try:
            # SIGTERM: kill 명령기본시그널
            signal.signal(signal.SIGTERM, cleanup_handler)
            # SIGINT: Ctrl+C
            signal.signal(signal.SIGINT, cleanup_handler)
            # SIGHUP: 터미널종료(만 Unix 시스템)
            if has_sighup:
                signal.signal(signal.SIGHUP, cleanup_handler)
        except ValueError:
            # 않에서주스레드중, 만수사용 atexit
            logger.warning("불가능등록시그널처리기(않에서주스레드), 만사용 atexit")
        
        _cleanup_registered = True
    
    @classmethod
    def get_running_simulations(cls) -> List[str]:
        """
        가져오기모든진행 중실행의시뮬레이션ID목록
        """
        running = []
        for sim_id, process in cls._processes.items():
            if process.poll() is None:
                running.append(sim_id)
        return running
    
    # ============== Interview 기능 ==============
    
    @classmethod
    def check_env_alive(cls, simulation_id: str) -> bool:
        """
        확인시뮬레이션환경여부존재하고 활성(가능수신Interview명령)

        Args:
            simulation_id: 시뮬레이션ID

        Returns:
            True 표시환경존재하고 활성, False 표시환경이미종료
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return False

        ipc_client = SimulationIPCClient(sim_dir)
        return ipc_client.check_env_alive()

    @classmethod
    def get_env_status_detail(cls, simulation_id: str) -> Dict[str, Any]:
        """
        가져오기시뮬레이션환경의상세상태정보

        Args:
            simulation_id: 시뮬레이션ID

        Returns:
            상태상세 정보딕셔너리, 포함 status, twitter_available, reddit_available, timestamp
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        status_file = os.path.join(sim_dir, "env_status.json")
        
        default_status = {
            "status": "stopped",
            "twitter_available": False,
            "reddit_available": False,
            "timestamp": None
        }
        
        if not os.path.exists(status_file):
            return default_status
        
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                status = json.load(f)
            return {
                "status": status.get("status", "stopped"),
                "twitter_available": status.get("twitter_available", False),
                "reddit_available": status.get("reddit_available", False),
                "timestamp": status.get("timestamp")
            }
        except (json.JSONDecodeError, OSError):
            return default_status

    @classmethod
    def interview_agent(
        cls,
        simulation_id: str,
        agent_id: int,
        prompt: str,
        platform: str = None,
        timeout: float = 60.0
    ) -> Dict[str, Any]:
        """
        인터뷰단개Agent

        Args:
            simulation_id: 시뮬레이션ID
            agent_id: Agent ID
            prompt: 인터뷰질문
            platform: 지정플랫폼(선택)
                - "twitter": 만인터뷰Twitter플랫폼
                - "reddit": 만인터뷰Reddit플랫폼
                - None: 이중플랫폼시뮬레이션시동시인터뷰2개플랫폼, 반환통합결과
            timeout: 타임아웃시간(초)

        Returns:
            인터뷰결과딕셔너리

        Raises:
            ValueError: 시뮬레이션존재하지 않음또는환경미실행
            TimeoutError: 대기응답타임아웃
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"시뮬레이션존재하지 않음: {simulation_id}")

        ipc_client = SimulationIPCClient(sim_dir)

        if not ipc_client.check_env_alive():
            raise ValueError(f"시뮬레이션환경미실행또는이미종료, 불가능실행Interview: {simulation_id}")

        logger.info(f"전송Interview명령: simulation_id={simulation_id}, agent_id={agent_id}, platform={platform}")

        response = ipc_client.send_interview(
            agent_id=agent_id,
            prompt=prompt,
            platform=platform,
            timeout=timeout
        )

        if response.status.value == "completed":
            return {
                "success": True,
                "agent_id": agent_id,
                "prompt": prompt,
                "result": response.result,
                "timestamp": response.timestamp
            }
        else:
            return {
                "success": False,
                "agent_id": agent_id,
                "prompt": prompt,
                "error": response.error,
                "timestamp": response.timestamp
            }
    
    @classmethod
    def interview_agents_batch(
        cls,
        simulation_id: str,
        interviews: List[Dict[str, Any]],
        platform: str = None,
        timeout: float = 120.0
    ) -> Dict[str, Any]:
        """
        일괄인터뷰다개Agent

        Args:
            simulation_id: 시뮬레이션ID
            interviews: 인터뷰목록, 각개요소포함 {"agent_id": int, "prompt": str, "platform": str(선택)}
            platform: 기본플랫폼(선택, 회된각개인터뷰 항목의platform덮어쓰기)
                - "twitter": 기본만인터뷰Twitter플랫폼
                - "reddit": 기본만인터뷰Reddit플랫폼
                - None: 이중플랫폼시뮬레이션시각개Agent동시인터뷰2개플랫폼
            timeout: 타임아웃시간(초)

        Returns:
            일괄인터뷰결과딕셔너리

        Raises:
            ValueError: 시뮬레이션존재하지 않음또는환경미실행
            TimeoutError: 대기응답타임아웃
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"시뮬레이션존재하지 않음: {simulation_id}")

        ipc_client = SimulationIPCClient(sim_dir)

        if not ipc_client.check_env_alive():
            raise ValueError(f"시뮬레이션환경미실행또는이미종료, 불가능실행Interview: {simulation_id}")

        logger.info(f"전송일괄Interview명령: simulation_id={simulation_id}, count={len(interviews)}, platform={platform}")

        response = ipc_client.send_batch_interview(
            interviews=interviews,
            platform=platform,
            timeout=timeout
        )

        if response.status.value == "completed":
            return {
                "success": True,
                "interviews_count": len(interviews),
                "result": response.result,
                "timestamp": response.timestamp
            }
        else:
            return {
                "success": False,
                "interviews_count": len(interviews),
                "error": response.error,
                "timestamp": response.timestamp
            }
    
    @classmethod
    def interview_all_agents(
        cls,
        simulation_id: str,
        prompt: str,
        platform: str = None,
        timeout: float = 180.0
    ) -> Dict[str, Any]:
        """
        인터뷰모든Agent(전체인터뷰)

        사용동일한의질문인터뷰시뮬레이션중의모든Agent

        Args:
            simulation_id: 시뮬레이션ID
            prompt: 인터뷰질문(모든Agent사용동일한질문)
            platform: 지정플랫폼(선택)
                - "twitter": 만인터뷰Twitter플랫폼
                - "reddit": 만인터뷰Reddit플랫폼
                - None: 이중플랫폼시뮬레이션시각개Agent동시인터뷰2개플랫폼
            timeout: 타임아웃시간(초)

        Returns:
            전체인터뷰결과딕셔너리
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"시뮬레이션존재하지 않음: {simulation_id}")

        # 에서설정파일가져오기모든Agent정보
        config_path = os.path.join(sim_dir, "simulation_config.json")
        if not os.path.exists(config_path):
            raise ValueError(f"시뮬레이션설정존재하지 않음: {simulation_id}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        agent_configs = config.get("agent_configs", [])
        if not agent_configs:
            raise ValueError(f"시뮬레이션설정중없있음Agent: {simulation_id}")

        # 구축일괄인터뷰목록
        interviews = []
        for agent_config in agent_configs:
            agent_id = agent_config.get("agent_id")
            if agent_id is not None:
                interviews.append({
                    "agent_id": agent_id,
                    "prompt": prompt
                })

        logger.info(f"전송전체Interview명령: simulation_id={simulation_id}, agent_count={len(interviews)}, platform={platform}")

        return cls.interview_agents_batch(
            simulation_id=simulation_id,
            interviews=interviews,
            platform=platform,
            timeout=timeout
        )
    
    @classmethod
    def close_simulation_env(
        cls,
        simulation_id: str,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        종료시뮬레이션환경(이 아닌중지시뮬레이션프로세스)
        
        시뮬레이션에전송종료환경명령, 그것이최아한종료대기명령모드
        
        Args:
            simulation_id: 시뮬레이션ID
            timeout: 타임아웃시간(초)
            
        Returns:
            작업결과딕셔너리
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"시뮬레이션존재하지 않음: {simulation_id}")
        
        ipc_client = SimulationIPCClient(sim_dir)
        
        if not ipc_client.check_env_alive():
            return {
                "success": True,
                "message": "환경이미경종료"
            }
        
        logger.info(f"전송종료환경명령: simulation_id={simulation_id}")
        
        try:
            response = ipc_client.send_close_env(timeout=timeout)
            
            return {
                "success": response.status.value == "completed",
                "message": "환경종료명령이미전송",
                "result": response.result,
                "timestamp": response.timestamp
            }
        except TimeoutError:
            # 타임아웃가수임때문에환경진행 중종료
            return {
                "success": True,
                "message": "환경종료명령이미전송(대기응답타임아웃, 환경가수진행 중종료)"
            }
    
    @classmethod
    def _get_interview_history_from_db(
        cls,
        db_path: str,
        platform_name: str,
        agent_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """에서단개데이터라이브러리가져오기Interview이력"""
        import sqlite3
        
        if not os.path.exists(db_path):
            return []
        
        results = []
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            if agent_id is not None:
                cursor.execute("""
                    SELECT user_id, info, created_at
                    FROM trace
                    WHERE action = 'interview' AND user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (agent_id, limit))
            else:
                cursor.execute("""
                    SELECT user_id, info, created_at
                    FROM trace
                    WHERE action = 'interview'
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
            
            for user_id, info_json, created_at in cursor.fetchall():
                try:
                    info = json.loads(info_json) if info_json else {}
                except json.JSONDecodeError:
                    info = {"raw": info_json}
                
                results.append({
                    "agent_id": user_id,
                    "response": info.get("response", info),
                    "prompt": info.get("prompt", ""),
                    "timestamp": created_at,
                    "platform": platform_name
                })
            
            conn.close()
            
        except Exception as e:
            logger.error(f"읽기Interview이력실패 ({platform_name}): {e}")
        
        return results

    @classmethod
    def get_interview_history(
        cls,
        simulation_id: str,
        platform: str = None,
        agent_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        가져오기Interview이력기록(에서데이터라이브러리읽기)
        
        Args:
            simulation_id: 시뮬레이션ID
            platform: 플랫폼유형(reddit/twitter/None)
                - "reddit": 만가져오기Reddit플랫폼의이력
                - "twitter": 만가져오기Twitter플랫폼의이력
                - None: 가져오기2개플랫폼의모든이력
            agent_id: 지정Agent ID(선택, 만가져오기해당Agent의이력)
            limit: 각개플랫폼반환수량제한
            
        Returns:
            Interview이력기록목록
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        
        results = []
        
        # 확정요조회의플랫폼
        if platform in ("reddit", "twitter"):
            platforms = [platform]
        else:
            # 않지정platform시, 조회2개플랫폼
            platforms = ["twitter", "reddit"]
        
        for p in platforms:
            db_path = os.path.join(sim_dir, f"{p}_simulation.db")
            platform_results = cls._get_interview_history_from_db(
                db_path=db_path,
                platform_name=p,
                agent_id=agent_id,
                limit=limit
            )
            results.extend(platform_results)
        
        # 시간순내림차순정렬
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # 만약조회함다개플랫폼, 제한총수
        if len(platforms) > 1 and len(results) > limit:
            results = results[:limit]
        
        return results

