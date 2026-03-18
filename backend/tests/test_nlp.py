from app.services.nlp import extract_domain_tags, keyword_matches_content


def test_extract_domain_tags_filters_ascii_url_noise_and_keeps_domain_terms():
    text = """
    https://graduate.sysu.edu.cn/example?id=2026
    中山大学 2026 年硕士研究生招生考试复试基本分数线公告
    请查看 pdf 附件与 graduate 页面说明。
    """

    tags = extract_domain_tags(text, top_k=6)

    assert "复试线" in tags
    assert "https" not in tags
    assert "graduate" not in tags
    assert "2026" not in tags


def test_keyword_matches_content_by_system_keyword_aliases():
    text = "中山大学 2026 年硕士研究生招生考试复试基本分数线公告"
    tags = ["复试线", "招生"]

    assert keyword_matches_content("复试线", text, tags) is True
    assert keyword_matches_content("复试分数线", text, tags) is True
    assert keyword_matches_content("拟录取", text, tags) is False
