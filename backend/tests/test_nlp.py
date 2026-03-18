from app.services.nlp import extract_domain_tags, infer_content_category, keyword_matches_content


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


def test_infer_content_category_promotes_adjustment_when_text_has_strong_signals():
    category = infer_content_category(
        title="XX大学关于接收2026年硕士研究生调剂的通知",
        summary="公布调剂缺额和申请方式",
        body="欢迎符合条件的考生通过全国硕士生招生调剂系统报名。",
        tags=["调剂", "缺额"],
        existing_category="announcement",
    )

    assert category == "adjustment"


def test_infer_content_category_keeps_regular_notice_as_announcement():
    category = infer_content_category(
        title="XX大学2026年硕士研究生复试基本分数线公告",
        summary="公布复试线和资格审查安排",
        body="请考生按时提交资格审查材料并参加复试。",
        tags=["复试线"],
        existing_category="announcement",
    )

    assert category == "announcement"
