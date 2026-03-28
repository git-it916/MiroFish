"""
OASIS Agent Profile 생성기
Zep 그래프의 엔티티를 OASIS 시뮬레이션 플랫폼에 필요한 Agent Profile 형식으로 변환

최적화 개선:
1. Zep 검색 기능을 호출하여 노드 정보를 2차적으로 보강
2. 프롬프트 최적화로 매우 상세한 페르소나 생성
3. 개인 엔티티와 추상 그룹 엔티티 구분
"""

import json
import random
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from openai import OpenAI
from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from .zep_entity_reader import EntityNode, ZepEntityReader

logger = get_logger('mirofish.oasis_profile')


@dataclass
class OasisAgentProfile:
    """OASIS Agent Profile데이터구조"""
    # 일반사용필드
    user_id: int
    user_name: str
    name: str
    bio: str
    persona: str
    
    # 선택필드 - Reddit스타일
    karma: int = 1000
    
    # 선택필드 - Twitter스타일
    friend_count: int = 100
    follower_count: int = 150
    statuses_count: int = 500
    
    # 추가페르소나정보
    age: Optional[int] = None
    gender: Optional[str] = None
    mbti: Optional[str] = None
    country: Optional[str] = None
    profession: Optional[str] = None
    interested_topics: List[str] = field(default_factory=list)
    
    # 출처엔티티정보
    source_entity_uuid: Optional[str] = None
    source_entity_type: Optional[str] = None
    
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    
    def to_reddit_format(self) -> Dict[str, Any]:
        """변환를Reddit플랫폼형식"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS 라이브러리요구필드명를 username(없음언더스코어)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "created_at": self.created_at,
        }
        
        # 추가추가페르소나정보(만약있음)
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        return profile
    
    def to_twitter_format(self) -> Dict[str, Any]:
        """변환를Twitter플랫폼형식"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS 라이브러리요구필드명를 username(없음언더스코어)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "created_at": self.created_at,
        }
        
        # 추가추가페르소나정보
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        return profile
    
    def to_dict(self) -> Dict[str, Any]:
        """변환를완전한딕셔너리형식"""
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "age": self.age,
            "gender": self.gender,
            "mbti": self.mbti,
            "country": self.country,
            "profession": self.profession,
            "interested_topics": self.interested_topics,
            "source_entity_uuid": self.source_entity_uuid,
            "source_entity_type": self.source_entity_type,
            "created_at": self.created_at,
        }


class OasisProfileGenerator:
    """
    OASIS Profile생성기
    
    을Zep그래프중의엔티티변환를OASIS시뮬레이션필요한의Agent Profile
    
    최적화특성: 
    1. 호출Zep그래프검색기능가져오기더풍부한의컨텍스트
    2. 생성매우상세의페르소나(포함기본정보, 직업 경력, 성격 특징, 소셜 미디어행를등)
    3. 개인 엔티티와 추상 그룹 엔티티 구분
    """
    
    # MBTI유형목록
    MBTI_TYPES = [
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP"
    ]
    
    # 일반적인국가목록
    COUNTRIES = [
        "China", "US", "UK", "Japan", "Germany", "France", 
        "Canada", "Australia", "Brazil", "India", "South Korea"
    ]
    
    # 개인유형엔티티(필요생성구체적페르소나)
    INDIVIDUAL_ENTITY_TYPES = [
        "student", "alumni", "professor", "person", "publicfigure", 
        "expert", "faculty", "official", "journalist", "activist"
    ]
    
    # 집단/기관유형엔티티(필요생성집단대표페르소나)
    GROUP_ENTITY_TYPES = [
        "university", "governmentagency", "organization", "ngo", 
        "mediaoutlet", "company", "institution", "group", "community"
    ]
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        zep_api_key: Optional[str] = None,
        graph_id: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model_name = model_name or Config.LLM_MODEL_NAME
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY 미설정")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        # Zep클라이언트사용되는검색풍부한컨텍스트
        self.zep_api_key = zep_api_key or Config.ZEP_API_KEY
        self.zep_client = None
        self.graph_id = graph_id
        
        if self.zep_api_key:
            try:
                self.zep_client = Zep(api_key=self.zep_api_key)
            except Exception as e:
                logger.warning(f"Zep클라이언트초기화실패: {e}")
    
    def generate_profile_from_entity(
        self, 
        entity: EntityNode, 
        user_id: int,
        use_llm: bool = True
    ) -> OasisAgentProfile:
        """
        에서Zep엔티티생성OASIS Agent Profile
        
        Args:
            entity: Zep엔티티노드
            user_id: 사용자ID(사용되는OASIS)
            use_llm: 여부사용LLM생성상세페르소나
            
        Returns:
            OasisAgentProfile
        """
        entity_type = entity.get_entity_type() or "Entity"
        
        # 기본정보
        name = entity.name
        user_name = self._generate_username(name)
        
        # 구축컨텍스트정보
        context = self._build_entity_context(entity)
        
        if use_llm:
            # 사용LLM생성상세페르소나
            profile_data = self._generate_profile_with_llm(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes,
                context=context
            )
        else:
            # 규칙 기반 생성기본페르소나
            profile_data = self._generate_profile_rule_based(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes
            )
        
        return OasisAgentProfile(
            user_id=user_id,
            user_name=user_name,
            name=name,
            bio=profile_data.get("bio", f"{entity_type}: {name}"),
            persona=profile_data.get("persona", entity.summary or f"A {entity_type} named {name}."),
            karma=profile_data.get("karma", random.randint(500, 5000)),
            friend_count=profile_data.get("friend_count", random.randint(50, 500)),
            follower_count=profile_data.get("follower_count", random.randint(100, 1000)),
            statuses_count=profile_data.get("statuses_count", random.randint(100, 2000)),
            age=profile_data.get("age"),
            gender=profile_data.get("gender"),
            mbti=profile_data.get("mbti"),
            country=profile_data.get("country"),
            profession=profile_data.get("profession"),
            interested_topics=profile_data.get("interested_topics", []),
            source_entity_uuid=entity.uuid,
            source_entity_type=entity_type,
        )
    
    def _generate_username(self, name: str) -> str:
        """생성사용자명"""
        # 제거특수문자, 변환를소문자
        username = name.lower().replace(" ", "_")
        username = ''.join(c for c in username if c.isalnum() or c == '_')
        
        # 추가랜덤접미사방지중복
        suffix = random.randint(100, 999)
        return f"{username}_{suffix}"
    
    def _search_zep_for_entity(self, entity: EntityNode) -> Dict[str, Any]:
        """
        사용Zep그래프하이브리드 검색기능가져오기엔티티관련의풍부한정보
        
        Zep없있음내장하이브리드 검색인터페이스, 필요분별검색edges및nodes그런 다음병합결과。
        사용병렬요청동시검색, 효율을 높입니다.
        
        Args:
            entity: 엔티티노드객체
            
        Returns:
            포함facts, node_summaries, context의딕셔너리
        """
        import concurrent.futures
        
        if not self.zep_client:
            return {"facts": [], "node_summaries": [], "context": ""}
        
        entity_name = entity.name
        
        results = {
            "facts": [],
            "node_summaries": [],
            "context": ""
        }
        
        # 필수있음graph_id할수진행검색
        if not self.graph_id:
            logger.debug(f"조건너뛰기Zep검색: 미설정graph_id")
            return results
        
        comprehensive_query = f"관련{entity_name}의모든정보, 활동, 이벤트, 관계및배경"
        
        def search_edges():
            """검색엣지(사실/관계)- 재시도 메커니즘 포함"""
            max_retries = 3
            last_exception = None
            delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    return self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=30,
                        scope="edges",
                        reranker="rrf"
                    )
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(f"Zep엣지 검색제 {attempt + 1} 회실패: {str(e)[:80]}, 재시도중...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"Zep엣지 검색에서 {max_retries} 회시도후에도실패: {e}")
            return None
        
        def search_nodes():
            """검색노드(엔티티요약)- 재시도 메커니즘 포함"""
            max_retries = 3
            last_exception = None
            delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    return self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=20,
                        scope="nodes",
                        reranker="rrf"
                    )
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(f"Zep노드검색제 {attempt + 1} 회실패: {str(e)[:80]}, 재시도중...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"Zep노드검색에서 {max_retries} 회시도후에도실패: {e}")
            return None
        
        try:
            # 병렬실행edges및nodes검색
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                edge_future = executor.submit(search_edges)
                node_future = executor.submit(search_nodes)
                
                # 가져오기결과
                edge_result = edge_future.result(timeout=30)
                node_result = node_future.result(timeout=30)
            
            # 처리엣지 검색결과
            all_facts = set()
            if edge_result and hasattr(edge_result, 'edges') and edge_result.edges:
                for edge in edge_result.edges:
                    if hasattr(edge, 'fact') and edge.fact:
                        all_facts.add(edge.fact)
            results["facts"] = list(all_facts)
            
            # 처리노드검색결과
            all_summaries = set()
            if node_result and hasattr(node_result, 'nodes') and node_result.nodes:
                for node in node_result.nodes:
                    if hasattr(node, 'summary') and node.summary:
                        all_summaries.add(node.summary)
                    if hasattr(node, 'name') and node.name and node.name != entity_name:
                        all_summaries.add(f"관련엔티티: {node.name}")
            results["node_summaries"] = list(all_summaries)
            
            # 구축종합컨텍스트
            context_parts = []
            if results["facts"]:
                context_parts.append("사실정보:\n" + "\n".join(f"- {f}" for f in results["facts"][:20]))
            if results["node_summaries"]:
                context_parts.append("관련엔티티:\n" + "\n".join(f"- {s}" for s in results["node_summaries"][:10]))
            results["context"] = "\n\n".join(context_parts)
            
            logger.info(f"Zep하이브리드검색완료: {entity_name}, 가져오기 {len(results['facts'])} 조건사실, {len(results['node_summaries'])} 개관련노드")
            
        except concurrent.futures.TimeoutError:
            logger.warning(f"Zep검색타임아웃 ({entity_name})")
        except Exception as e:
            logger.warning(f"Zep검색실패 ({entity_name}): {e}")
        
        return results
    
    def _build_entity_context(self, entity: EntityNode) -> str:
        """
        구축엔티티의완전한컨텍스트정보
        
        포함: 
        1. 엔티티자체의엣지 정보(사실)
        2. 연관노드의상세정보
        3. Zep하이브리드검색까지의풍부한정보
        """
        context_parts = []
        
        # 1. 추가엔티티속성정보
        if entity.attributes:
            attrs = []
            for key, value in entity.attributes.items():
                if value and str(value).strip():
                    attrs.append(f"- {key}: {value}")
            if attrs:
                context_parts.append("### 엔티티속성\n" + "\n".join(attrs))
        
        # 2. 추가관련엣지 정보(사실/관계)
        existing_facts = set()
        if entity.related_edges:
            relationships = []
            for edge in entity.related_edges:  # 않제한수량
                fact = edge.get("fact", "")
                edge_name = edge.get("edge_name", "")
                direction = edge.get("direction", "")
                
                if fact:
                    relationships.append(f"- {fact}")
                    existing_facts.add(fact)
                elif edge_name:
                    if direction == "outgoing":
                        relationships.append(f"- {entity.name} --[{edge_name}]--> (관련엔티티)")
                    else:
                        relationships.append(f"- (관련엔티티) --[{edge_name}]--> {entity.name}")
            
            if relationships:
                context_parts.append("### 관련사실및관계\n" + "\n".join(relationships))
        
        # 3. 추가연관노드의상세정보
        if entity.related_nodes:
            related_info = []
            for node in entity.related_nodes:  # 않제한수량
                node_name = node.get("name", "")
                node_labels = node.get("labels", [])
                node_summary = node.get("summary", "")
                
                # 필터링하여 제거기본라벨
                custom_labels = [l for l in node_labels if l not in ["Entity", "Node"]]
                label_str = f" ({', '.join(custom_labels)})" if custom_labels else ""
                
                if node_summary:
                    related_info.append(f"- **{node_name}**{label_str}: {node_summary}")
                else:
                    related_info.append(f"- **{node_name}**{label_str}")
            
            if related_info:
                context_parts.append("### 연관엔티티정보\n" + "\n".join(related_info))
        
        # 4. 사용Zep하이브리드검색가져오기더풍부한의정보
        zep_results = self._search_zep_for_entity(entity)
        
        if zep_results.get("facts"):
            # 중복 제거: 제외이미존에서의사실
            new_facts = [f for f in zep_results["facts"] if f not in existing_facts]
            if new_facts:
                context_parts.append("### Zep검색까지의사실정보\n" + "\n".join(f"- {f}" for f in new_facts[:15]))
        
        if zep_results.get("node_summaries"):
            context_parts.append("### Zep검색까지의관련노드\n" + "\n".join(f"- {s}" for s in zep_results["node_summaries"][:10]))
        
        return "\n\n".join(context_parts)
    
    def _is_individual_entity(self, entity_type: str) -> bool:
        """판단여부임개인유형엔티티"""
        return entity_type.lower() in self.INDIVIDUAL_ENTITY_TYPES
    
    def _is_group_entity(self, entity_type: str) -> bool:
        """판단여부임집단/기관유형엔티티"""
        return entity_type.lower() in self.GROUP_ENTITY_TYPES
    
    def _generate_profile_with_llm(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """
        사용LLM생성매우상세의페르소나
        
        에 따라엔티티유형구분: 
        - 개인엔티티: 생성구체적의인물설정
        - 집단/기관엔티티: 생성대표성계정설정
        """
        
        is_individual = self._is_individual_entity(entity_type)
        
        if is_individual:
            prompt = self._build_individual_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
        else:
            prompt = self._build_group_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )

        # 시도다회생성, 직까지성공또는달까지최대재시도회수
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": self._get_system_prompt(is_individual)},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1)  # 매 재시도마다 온도 낮춤
                    # 않설정max_tokens, 하여LLM자유발휘
                )
                
                content = response.choices[0].message.content
                
                # 확인여부된잘림(finish_reason않임'stop')
                finish_reason = response.choices[0].finish_reason
                if finish_reason == 'length':
                    logger.warning(f"LLM 출력이 잘림 (attempt {attempt+1}), 시도수정...")
                    content = self._fix_truncated_json(content)
                
                # 시도파싱JSON
                try:
                    result = json.loads(content)
                    
                    # 검증필수필드
                    if "bio" not in result or not result["bio"]:
                        result["bio"] = entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}"
                    if "persona" not in result or not result["persona"]:
                        result["persona"] = entity_summary or f"{entity_name}은(는) {entity_type}。"
                    
                    return result
                    
                except json.JSONDecodeError as je:
                    logger.warning(f"JSON 파싱 실패 (attempt {attempt+1}): {str(je)[:80]}")
                    
                    # 시도수정JSON
                    result = self._try_fix_json(content, entity_name, entity_type, entity_summary)
                    if result.get("_fixed"):
                        del result["_fixed"]
                        return result
                    
                    last_error = je
                    
            except Exception as e:
                logger.warning(f"LLM 호출 실패 (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(1 * (attempt + 1))  # 지수 백오프
        
        logger.warning(f"LLM생성페르소나실패({max_attempts}회시도): {last_error}, 규칙 기반 생성")
        return self._generate_profile_rule_based(
            entity_name, entity_type, entity_summary, entity_attributes
        )
    
    def _fix_truncated_json(self, content: str) -> str:
        """잘린 JSON 수정(출력된max_tokens제한잘림)"""
        import re
        
        # 만약JSON된잘림, 시도닫기
        content = content.strip()
        
        # 계산미닫기의괄호
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        # 확인여부있음미닫기의문자열
        # 간단확인: 만약가장후일개인용부호후없있음쉼표또는닫기괄호, 가수임문자열된잘림
        if content and content[-1] not in '",}]':
            # 시도닫기문자열
            content += '"'
        
        # 닫기괄호
        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content
    
    def _try_fix_json(self, content: str, entity_name: str, entity_type: str, entity_summary: str = "") -> Dict[str, Any]:
        """시도수정손상의JSON"""
        import re
        
        # 1. 먼저시도잘린 상황 수정
        content = self._fix_truncated_json(content)
        
        # 2. 시도추출JSON일부
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            
            # 3. 처리문자열중의줄바꿈질문
            # 찾은모든문자열값및 교체이 중의줄바꿈
            def fix_string_newlines(match):
                s = match.group(0)
                # 교체문자열내의실제줄바꿈를공백
                s = s.replace('\n', ' ').replace('\r', ' ')
                # 교체불필요한공백
                s = re.sub(r'\s+', ' ', s)
                return s
            
            # 매칭JSON문자열값
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string_newlines, json_str)
            
            # 4. 시도파싱
            try:
                result = json.loads(json_str)
                result["_fixed"] = True
                return result
            except json.JSONDecodeError as e:
                # 5. 만약아직임실패, 시도더분진의수정
                try:
                    # 제거모든제어 문자
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                    # 교체모든연속공백
                    json_str = re.sub(r'\s+', ' ', json_str)
                    result = json.loads(json_str)
                    result["_fixed"] = True
                    return result
                except:
                    pass
        
        # 6. 시도에서내용중추출일부정보
        bio_match = re.search(r'"bio"\s*:\s*"([^"]*)"', content)
        persona_match = re.search(r'"persona"\s*:\s*"([^"]*)', content)  # 가수된잘림
        
        bio = bio_match.group(1) if bio_match else (entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}")
        persona = persona_match.group(1) if persona_match else (entity_summary or f"{entity_name}은(는) {entity_type}。")
        
        # 만약추출까지함있음의미 있는의내용, 표시를수정됨
        if bio_match or persona_match:
            logger.info(f"에서손상의JSON중추출함일부정보")
            return {
                "bio": bio,
                "persona": persona,
                "_fixed": True
            }
        
        # 7. 완전실패, 반환기본구조
        logger.warning(f"JSON수정실패, 반환기본구조")
        return {
            "bio": entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}",
            "persona": entity_summary or f"{entity_name}은(는) {entity_type}。"
        }
    
    def _get_system_prompt(self, is_individual: bool) -> str:
        """가져오기시스템 프롬프트"""
        base_prompt = "당신은소셜 미디어사용자 프로필생성전문가。생성상세, 사실적의페르소나사용되는여론시뮬레이션,최대한도복원기존현실 상황。필수반환있음효의JSON형식, 모든문자열값불가포함미이스케이프의의줄바꿈。모든출력필드의내용필수사용한언(한국어)。"
        return base_prompt
    
    def _build_individual_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """구축개인엔티티의상세페르소나프롬프트"""
        
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "없음"
        context_str = context[:3000] if context else "없음추가컨텍스트"
        
        return f"""를엔티티생성상세의소셜 미디어사용자페르소나,최대한도복원기존현실 상황。

엔티티이름: {entity_name}
엔티티유형: {entity_type}
엔티티요약: {entity_summary}
엔티티속성: {attrs_str}

컨텍스트정보:
{context_str}

생성하세요JSON, 포함다음 필드:

1. bio: 소셜 미디어소개, 200문자
2. persona: 상세페르소나설명(2000문자의순텍스트), 필요포함:
   - 기본정보(나이, 직업, 교육배경, 소재지)
   - 인물배경(중요경력, 와이벤트의연관, 소회관계)
   - 성격 특징(MBTI유형, 핵심성격, 감정표달식식)
   - 소셜 미디어행를(게시빈도, 내용선호, 상호작용스타일, 언어특시)
   - 입장관점(대화제의태도, 가수된분노/감작용의내용)
   - 독특특징(말버릇, 특수경력, 개인취호)
   - 개인메모리(페르소나의중요일부, 요소개이개디어와이벤트의연관, 및이개디어에서이벤트중의기존동작와반응)
3. age: 나이수문자(필수임정수)
4. gender: 성별, 필수임영문: "male" 또는 "female"
5. mbti: MBTI유형(예INTJ, ENFP등)
6. country: 국가(사용한언, 예"한국", "미국")
7. profession: 직업
8. interested_topics: 관심화제배열

중요:
- 모든필드값필수임문자열또는수문자, 않요사용줄바꿈
- persona필수임일대연관된의텍스트문자설명
- 모든출력내용필수사용한언(한국어), 포함bio, persona, profession, country, interested_topics등필드
- gender필드필수사용영문male/female
- country필드사용한언, 예"한국", "미국", "중국"→"중국"가쓰기를"중국"
- 내용요와엔티티정보유지일래
- age필수임있음효의정수, gender필수임"male"또는"female"
"""

    def _build_group_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """구축집단/기관엔티티의상세페르소나프롬프트"""
        
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "없음"
        context_str = context[:3000] if context else "없음추가컨텍스트"
        
        return f"""를기관/집단엔티티생성상세의소셜 미디어계정설정,최대한도복원기존현실 상황。

엔티티이름: {entity_name}
엔티티유형: {entity_type}
엔티티요약: {entity_summary}
엔티티속성: {attrs_str}

컨텍스트정보:
{context_str}

생성하세요JSON, 포함다음 필드:

1. bio: 공식계정소개, 200문자, 전업품위디어
2. persona: 상세계정설정설명(2000문자의순텍스트), 필요포함:
   - 기관기본정보(올식이름, 기관성질, 설립배경, 주요직수)
   - 계정정위(계정유형, 목표수중, 핵심기능)
   - 발어스타일(언어특시, 상사용표달, 금기화제)
   - 발포내용특시(내용유형, 발포빈도, 활성시간대)
   - 입장태도(대핵심화제의공식입장, 면대논쟁의처리식식)
   - 특수설명(대표의집단프로필, 운영습관)
   - 기관메모리(기관페르소나의중요일부, 요소개이기관와이벤트의연관, 및이기관에서이벤트중의기존동작와반응)
3. age: 고정값30(기관계정의가상나이)
4. gender: 고정값"other"(기관계정사용other표시비개인)
5. mbti: MBTI유형, 사용되는설명계정스타일, 예ISTJ대표엄격하고 보수적
6. country: 국가(사용한언, 예"한국", "미국")
7. profession: 기관직수설명
8. interested_topics: 관심분야배열

중요:
- 모든필드값필수임문자열또는수문자, 않허용null값
- persona필수임일대연관된의텍스트문자설명, 않요사용줄바꿈
- 모든출력내용필수사용한언(한국어), 포함bio, persona, profession, country, interested_topics등필드
- gender필드필수사용영문"other"
- country필드사용한언, 예"한국"
- age필수임정수30, gender필수임문자열"other"
- 기관계정발어요부합하는그신분 포지셔닝"""
    
    def _generate_profile_rule_based(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """규칙 기반 생성기본페르소나"""
        
        # 에 따라엔티티유형생성다른페르소나
        entity_type_lower = entity_type.lower()
        
        if entity_type_lower in ["student", "alumni"]:
            return {
                "bio": f"{entity_type} with interests in academics and social issues.",
                "persona": f"{entity_name} is a {entity_type.lower()} who is actively engaged in academic and social discussions. They enjoy sharing perspectives and connecting with peers.",
                "age": random.randint(18, 30),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": "Student",
                "interested_topics": ["Education", "Social Issues", "Technology"],
            }
        
        elif entity_type_lower in ["publicfigure", "expert", "faculty"]:
            return {
                "bio": f"Expert and thought leader in their field.",
                "persona": f"{entity_name} is a recognized {entity_type.lower()} who shares insights and opinions on important matters. They are known for their expertise and influence in public discourse.",
                "age": random.randint(35, 60),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(["ENTJ", "INTJ", "ENTP", "INTP"]),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_attributes.get("occupation", "Expert"),
                "interested_topics": ["Politics", "Economics", "Culture & Society"],
            }
        
        elif entity_type_lower in ["mediaoutlet", "socialmediaplatform"]:
            return {
                "bio": f"Official account for {entity_name}. News and updates.",
                "persona": f"{entity_name} is a media entity that reports news and facilitates public discourse. The account shares timely updates and engages with the audience on current events.",
                "age": 30,  # 기관가상나이
                "gender": "other",  # 기관사용other
                "mbti": "ISTJ",  # 기관스타일: 엄격하고 보수적
                "country": "중국",
                "profession": "Media",
                "interested_topics": ["General News", "Current Events", "Public Affairs"],
            }
        
        elif entity_type_lower in ["university", "governmentagency", "ngo", "organization"]:
            return {
                "bio": f"Official account of {entity_name}.",
                "persona": f"{entity_name} is an institutional entity that communicates official positions, announcements, and engages with stakeholders on relevant matters.",
                "age": 30,  # 기관가상나이
                "gender": "other",  # 기관사용other
                "mbti": "ISTJ",  # 기관스타일: 엄격하고 보수적
                "country": "중국",
                "profession": entity_type,
                "interested_topics": ["Public Policy", "Community", "Official Announcements"],
            }
        
        else:
            # 기본페르소나
            return {
                "bio": entity_summary[:150] if entity_summary else f"{entity_type}: {entity_name}",
                "persona": entity_summary or f"{entity_name} is a {entity_type.lower()} participating in social discussions.",
                "age": random.randint(25, 50),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_type,
                "interested_topics": ["General", "Social Issues"],
            }
    
    def set_graph_id(self, graph_id: str):
        """설정그래프ID사용되는Zep검색"""
        self.graph_id = graph_id
    
    def generate_profiles_from_entities(
        self,
        entities: List[EntityNode],
        use_llm: bool = True,
        progress_callback: Optional[callable] = None,
        graph_id: Optional[str] = None,
        parallel_count: int = 5,
        realtime_output_path: Optional[str] = None,
        output_platform: str = "reddit"
    ) -> List[OasisAgentProfile]:
        """
        일괄에서엔티티생성Agent Profile(지원병렬생성)
        
        Args:
            entities: 엔티티목록
            use_llm: 여부사용LLM생성상세페르소나
            progress_callback: 진행 상황콜백함수 (current, total, message)
            graph_id: 그래프ID, 사용되는Zep검색가져오기더풍부한컨텍스트
            parallel_count: 병렬생성수량, 기본5
            realtime_output_path: 실시간쓰기의파일경로(만약제공, 각생성일개바로 쓰기한 번)
            output_platform: 출력플랫폼형식 ("reddit" 또는 "twitter")
            
        Returns:
            Agent Profile목록
        """
        import concurrent.futures
        from threading import Lock
        
        # 설정graph_id사용되는Zep검색
        if graph_id:
            self.graph_id = graph_id
        
        total = len(entities)
        profiles = [None] * total  # 사전분정목록유지순서
        completed_count = [0]  # 사용목록위해에서클로저중수정
        lock = Lock()
        
        # 실시간쓰기파일의보조함수
        def save_profiles_realtime():
            """실시간저장이미생성의 profiles 까지파일"""
            if not realtime_output_path:
                return
            
            with lock:
                # 필터링이미생성의 profiles
                existing_profiles = [p for p in profiles if p is not None]
                if not existing_profiles:
                    return
                
                try:
                    if output_platform == "reddit":
                        # Reddit JSON 형식
                        profiles_data = [p.to_reddit_format() for p in existing_profiles]
                        with open(realtime_output_path, 'w', encoding='utf-8') as f:
                            json.dump(profiles_data, f, ensure_ascii=False, indent=2)
                    else:
                        # Twitter CSV 형식
                        import csv
                        profiles_data = [p.to_twitter_format() for p in existing_profiles]
                        if profiles_data:
                            fieldnames = list(profiles_data[0].keys())
                            with open(realtime_output_path, 'w', encoding='utf-8', newline='') as f:
                                writer = csv.DictWriter(f, fieldnames=fieldnames)
                                writer.writeheader()
                                writer.writerows(profiles_data)
                except Exception as e:
                    logger.warning(f"실시간저장 profiles 실패: {e}")
        
        def generate_single_profile(idx: int, entity: EntityNode) -> tuple:
            """생성단개profile의작업함수"""
            entity_type = entity.get_entity_type() or "Entity"
            
            try:
                profile = self.generate_profile_from_entity(
                    entity=entity,
                    user_id=idx,
                    use_llm=use_llm
                )
                
                # 실시간출력생성의페르소나까지콘솔및로그
                self._print_generated_profile(entity.name, entity_type, profile)
                
                return idx, profile, None
                
            except Exception as e:
                logger.error(f"생성엔티티 {entity.name} 의페르소나실패: {str(e)}")
                # 생성일개기본profile
                fallback_profile = OasisAgentProfile(
                    user_id=idx,
                    user_name=self._generate_username(entity.name),
                    name=entity.name,
                    bio=f"{entity_type}: {entity.name}",
                    persona=entity.summary or f"A participant in social discussions.",
                    source_entity_uuid=entity.uuid,
                    source_entity_type=entity_type,
                )
                return idx, fallback_profile, str(e)
        
        logger.info(f"시작병렬생성 {total} 개Agent페르소나(병렬수: {parallel_count})...")
        print(f"\n{'='*60}")
        print(f"시작생성Agent페르소나 - 총 {total} 개엔티티, 병렬수: {parallel_count}")
        print(f"{'='*60}\n")
        
        # 사용스레드풀병렬실행
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_count) as executor:
            # 제출모든태스크
            future_to_entity = {
                executor.submit(generate_single_profile, idx, entity): (idx, entity)
                for idx, entity in enumerate(entities)
            }
            
            # 수집결과
            for future in concurrent.futures.as_completed(future_to_entity):
                idx, entity = future_to_entity[future]
                entity_type = entity.get_entity_type() or "Entity"
                
                try:
                    result_idx, profile, error = future.result()
                    profiles[result_idx] = profile
                    
                    with lock:
                        completed_count[0] += 1
                        current = completed_count[0]
                    
                    # 실시간쓰기파일
                    save_profiles_realtime()
                    
                    if progress_callback:
                        progress_callback(
                            current, 
                            total, 
                            f"이미완료 {current}/{total}: {entity.name}({entity_type})"
                        )
                    
                    if error:
                        logger.warning(f"[{current}/{total}] {entity.name} 사용백업페르소나: {error}")
                    else:
                        logger.info(f"[{current}/{total}] 성공생성페르소나: {entity.name} ({entity_type})")
                        
                except Exception as e:
                    logger.error(f"처리엔티티 {entity.name} 시발생예외: {str(e)}")
                    with lock:
                        completed_count[0] += 1
                    profiles[idx] = OasisAgentProfile(
                        user_id=idx,
                        user_name=self._generate_username(entity.name),
                        name=entity.name,
                        bio=f"{entity_type}: {entity.name}",
                        persona=entity.summary or "A participant in social discussions.",
                        source_entity_uuid=entity.uuid,
                        source_entity_type=entity_type,
                    )
                    # 실시간쓰기파일(설령백업페르소나)
                    save_profiles_realtime()
        
        print(f"\n{'='*60}")
        print(f"페르소나생성완료！총생성 {len([p for p in profiles if p])} 개Agent")
        print(f"{'='*60}\n")
        
        return profiles
    
    def _print_generated_profile(self, entity_name: str, entity_type: str, profile: OasisAgentProfile):
        """실시간출력생성의페르소나까지콘솔(완전한내용, 않잘림)"""
        separator = "-" * 70
        
        # 구축완전한출력내용(않잘림)
        topics_str = ', '.join(profile.interested_topics) if profile.interested_topics else '없음'
        
        output_lines = [
            f"\n{separator}",
            f"[이미생성] {entity_name} ({entity_type})",
            f"{separator}",
            f"사용자명: {profile.user_name}",
            f"",
            f"【소개】",
            f"{profile.bio}",
            f"",
            f"【상세페르소나】",
            f"{profile.persona}",
            f"",
            f"【기본속성】",
            f"나이: {profile.age} | 성별: {profile.gender} | MBTI: {profile.mbti}",
            f"직업: {profile.profession} | 국가: {profile.country}",
            f"관심화제: {topics_str}",
            separator
        ]
        
        output = "\n".join(output_lines)
        
        # 만출력까지콘솔(방지중복, logger않다시출력완전한내용)
        print(output)
    
    def save_profiles(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """
        저장Profile까지파일(에 따라플랫폼정상 형식 선택형식)
        
        OASIS플랫폼형식요구: 
        - Twitter: CSV형식
        - Reddit: JSON형식
        
        Args:
            profiles: Profile목록
            file_path: 파일경로
            platform: 플랫폼유형 ("reddit" 또는 "twitter")
        """
        if platform == "twitter":
            self._save_twitter_csv(profiles, file_path)
        else:
            self._save_reddit_json(profiles, file_path)
    
    def _save_twitter_csv(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        저장Twitter Profile를CSV형식(부합하는OASIS공식요구)
        
        OASIS Twitter요구의CSV필드: 
        - user_id: 사용자ID(에 따라CSV순서에서0시작)
        - name: 사용자사실적이름명
        - username: 시스템중의사용자명
        - user_char: 상세페르소나설명(주입까지LLM시스템 프롬프트중, 지초Agent행를)
        - description: 간약의공개소개(표시에서사용자프로필 페이지)
        
        user_char vs description 구별: 
        - user_char: 내부사용, LLM시스템 프롬프트, 결정Agent어떻게 사고및행작용
        - description: 외부표시, 기타사용자가일반의소개
        """
        import csv
        
        # 보장파일확표명임.csv
        if not file_path.endswith('.csv'):
            file_path = file_path.replace('.json', '.csv')
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 쓰기OASIS요구의표버릇
            headers = ['user_id', 'name', 'username', 'user_char', 'description']
            writer.writerow(headers)
            
            # 쓰기데이터행
            for idx, profile in enumerate(profiles):
                # user_char: 완전한페르소나(bio + persona), 사용되는LLM시스템 프롬프트
                user_char = profile.bio
                if profile.persona and profile.persona != profile.bio:
                    user_char = f"{profile.bio} {profile.persona}"
                # 처리줄바꿈(CSV중사용공백 대체)
                user_char = user_char.replace('\n', ' ').replace('\r', ' ')
                
                # description: 간약소개, 사용되는외부표시
                description = profile.bio.replace('\n', ' ').replace('\r', ' ')
                
                row = [
                    idx,                    # user_id: 에서0시작의순서ID
                    profile.name,           # name: 사실적이름명
                    profile.user_name,      # username: 사용자명
                    user_char,              # user_char: 완전한페르소나(내부LLM사용)
                    description             # description: 간약소개(외부표시)
                ]
                writer.writerow(row)
        
        logger.info(f"이미저장 {len(profiles)} 개Twitter Profile까지 {file_path} (OASIS CSV형식)")
    
    def _normalize_gender(self, gender: Optional[str]) -> str:
        """
        표준적화gender필드를OASIS요구의영문형식
        
        OASIS요구: male, female, other
        """
        if not gender:
            return "other"
        
        gender_lower = gender.lower().strip()
        
        # 중텍스트매핑
        gender_map = {
            "남성": "male",
            "여성": "female",
            "기관": "other",
            "기타": "other",
            # 영문기존
            "male": "male",
            "female": "female",
            "other": "other",
        }
        
        return gender_map.get(gender_lower, "other")
    
    def _save_reddit_json(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        저장Reddit Profile를JSON형식
        
        사용와 to_reddit_format() 일래의형식, 보장 OASIS 수정상읽기。
        필수포함 user_id 필드, 이것임 OASIS agent_graph.get_agent() 매칭의관건！
        
        필수필드: 
        - user_id: 사용자ID(정수, 사용되는매칭 initial_posts 중의 poster_agent_id)
        - username: 사용자명
        - name: 표시이름
        - bio: 소개
        - persona: 상세페르소나
        - age: 나이(정수)
        - gender: "male", "female", 또는 "other"
        - mbti: MBTI유형
        - country: 국가
        """
        data = []
        for idx, profile in enumerate(profiles):
            # 사용와 to_reddit_format() 일래의형식
            item = {
                "user_id": profile.user_id if profile.user_id is not None else idx,  # 관건: 필수포함 user_id
                "username": profile.user_name,
                "name": profile.name,
                "bio": profile.bio[:150] if profile.bio else f"{profile.name}",
                "persona": profile.persona or f"{profile.name} is a participant in social discussions.",
                "karma": profile.karma if profile.karma else 1000,
                "created_at": profile.created_at,
                # OASIS필수필드 - 보장모두있음기본값
                "age": profile.age if profile.age else 30,
                "gender": self._normalize_gender(profile.gender),
                "mbti": profile.mbti if profile.mbti else "ISTJ",
                "country": profile.country if profile.country else "중국",
            }
            
            # 선택필드
            if profile.profession:
                item["profession"] = profile.profession
            if profile.interested_topics:
                item["interested_topics"] = profile.interested_topics
            
            data.append(item)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"이미저장 {len(profiles)} 개Reddit Profile까지 {file_path} (JSON형식, 포함user_id필드)")
    
    # 유지기존 메서드명으로를별칭, 유지하위 호환
    def save_profiles_to_json(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """[이미폐기] 사용하세요 save_profiles() 메서드"""
        logger.warning("save_profiles_to_json이미폐기, 사용하세요save_profiles메서드")
        self.save_profiles(profiles, file_path, platform)

