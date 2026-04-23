"""

"""

from __future__ import annotations

from agent.core.schemas import ContentSource, TrustLevel, TrustTaggedContent

"""定义了一个默认的内容来源到信任级别的映射字典"""
DEFAULT_TRUST_MAPPING: dict[ContentSource,TrustLevel] = {
    ContentSource.SYSTEM: TrustLevel.TRUSTED,
    ContentSource.AGENT: TrustLevel.UNTRUSTED,
    ContentSource.USER: TrustLevel.UNTRUSTED,
    ContentSource.TOOL: TrustLevel.UNTRUSTED,
    ContentSource.RETRIEVER: TrustLevel.UNTRUSTED,
}

def get_default_trust_level(source: ContentSource) -> TrustLevel:
    """根据内容来源获取默认的信任级别"""
    return DEFAULT_TRUST_MAPPING.get(source, TrustLevel.UNTRUSTED)

def tag_content(content: str, source: ContentSource,metadata: dict | None = None) -> TrustTaggedContent:
    """根据内容来源为内容打上信任标签"""
    trust_level = get_default_trust_level(source)
    return TrustTaggedContent(content=content, source=source, trust_level=trust_level, metadata=metadata or {})

def mark_as_sanitized(tagged_content: TrustTaggedContent, metadata: dict | None = None) -> TrustTaggedContent:
    """将内容标记为已清洗，并更新相关的元数据"""
    merged_metadata = dict(tagged_content.metadata)
    if metadata:
        merged_metadata.update(metadata)
    
    return TrustTaggedContent(content=tagged_content.content, source=tagged_content.source, trust_level=TrustLevel.SANITIZED, metadata=merged_metadata)

def is_trusted(tagged_content: TrustTaggedContent) -> bool:
    """判断内容是否可信"""
    return tagged_content.trust_level == TrustLevel.TRUSTED

def is_untrusted(tagged_content: TrustTaggedContent) -> bool:
    """判断内容是否不可信"""
    return tagged_content.trust_level == TrustLevel.UNTRUSTED

def is_sanitized(tagged_content: TrustTaggedContent) -> bool:
    """判断内容是否已清洗"""
    return tagged_content.trust_level == TrustLevel.SANITIZED