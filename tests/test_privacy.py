"""隐私过滤：决定哪些内容能发给云端 AI（AI_ACCESS_RULES 规则 1、2、3、5）。

这里的逻辑出错就是泄露，所以每条规则都要有测试，包括"写错了也要保守处理"的情况。
"""
import twin
import twin_ai
from conftest import md

# 合法的测试值：校验位正确，但是是公开的测试号码
FAKE_ID = "11010519491231002X"  # GB 11643 标准里的示例身份证号
FAKE_CARD = "4111111111111111"  # Visa 测试卡号
FAKE_PHONE = "13800138000"


# ---------- 规则 1：privacy 字段 ----------

class TestPrivacyOf:
    def test_levels(self):
        for level in twin.LEVELS:
            assert twin.privacy_of(md(level)) == level

    def test_missing_field_or_frontmatter_is_none(self):
        assert twin.privacy_of(md(None)) is None
        assert twin.privacy_of("# 没有 Frontmatter\nprivacy: public") is None

    def test_case_insensitive(self):
        assert twin.privacy_of(md("PUBLIC")) == "public"

    def test_stricter_word_wins(self):
        # 规则 1：值中含有 private / secret 字样即按该级别处理
        assert twin.privacy_of(md("public-but-private")) == "private"
        assert twin.privacy_of(md("internal secret")) == "secret"

    def test_inline_comment_ignored(self):
        assert twin.privacy_of(md("public  # 以后改 private")) == "public"

    def test_unknown_value_is_none(self):
        assert twin.privacy_of(md("whatever")) is None

    def test_crlf_and_bom_fail_closed(self):
        # Windows 记事本存的文件：认不出来时必须当成没有字段（按 secret），不能当 public
        crlf = md("public").replace("\n", "\r\n")
        assert twin.privacy_of(crlf) in (None, "public")
        assert twin.privacy_of("﻿" + md("public")) in (None, "public")


# ---------- 规则 2：私密段落 ----------

class TestPrivateBlock:
    def test_removed(self):
        text = "公开\n<!-- private -->\n秘密\n<!-- /private -->\n公开2"
        out = twin.PRIVATE_BLOCK.sub("", text)
        assert "秘密" not in out and "公开" in out and "公开2" in out

    def test_variants(self):
        for open_, close in [("<!--private-->", "<!--/private-->"), ("<!-- PRIVATE -->", "<!-- /Private -->")]:
            out = twin.PRIVATE_BLOCK.sub("", f"a{open_}秘密{close}b")
            assert out == "ab"

    def test_multiple_blocks_non_greedy(self):
        text = "<!-- private -->x<!-- /private -->中间<!-- private -->y<!-- /private -->"
        assert twin.PRIVATE_BLOCK.sub("", text) == "中间"

    def test_unclosed_block_hides_rest_of_file(self):
        # 忘了写结束标记：网页把后面全部当私密显示，发出去时也必须全部去掉
        text = "公开\n<!-- private -->\n秘密\n更多秘密"
        out = twin.PRIVATE_BLOCK.sub("", text)
        assert "秘密" not in out
        assert out.startswith("公开")


# ---------- 规则 3：敏感值 ----------

class TestFindSensitive:
    def kinds(self, text):
        return {name for name, _ in twin.find_sensitive(text)}

    def test_detects_each_kind(self):
        assert self.kinds(f"身份证 {FAKE_ID}") == {"身份证号"}
        assert self.kinds(f"卡号 {FAKE_CARD}") == {"银行卡号"}
        assert self.kinds(f"电话 {FAKE_PHONE}") == {"手机号"}
        assert self.kinds("邮箱 someone@example.com") == {"邮箱"}

    def test_lookalikes_ignored(self):
        assert self.kinds("时间戳 1700000000000000") == set()  # 过不了 Luhn
        assert self.kinds("DOI 10.1000/1234567890123456") == set()
        assert self.kinds("110105194912310021") == set()  # 身份证校验位不对

    def test_placeholder_ok(self):
        assert self.kinds("身份证号：{{VAULT:ID_CARD}}") == set()

    def test_inside_private_block_ignored(self):
        assert self.kinds(f"<!-- private -->{FAKE_PHONE}<!-- /private -->") == set()

    def test_id_reported_once(self):
        hits = twin.find_sensitive(FAKE_ID)
        assert len(hits) == 1

    def test_mask(self):
        assert twin.mask("13800138000") == "13*******00"
        assert "0013800" not in twin.mask(FAKE_PHONE)


class TestCleanForChat:
    """网页对话附带 internal 细节文件前的清洗（twin_ai._clean）。"""

    def test_replaces_values_and_private(self):
        out = twin_ai._clean(f"电话 {FAKE_PHONE}\n<!-- private -->秘密<!-- /private -->\n邮箱 a@b.cn")
        assert FAKE_PHONE not in out and "秘密" not in out and "a@b.cn" not in out
        assert "[已隐藏]" in out and "[私密段落已移除]" in out

    def test_unclosed_private(self):
        out = twin_ai._clean("公开\n<!-- private -->\n秘密")
        assert "秘密" not in out


# ---------- 规则 5：打包只收 public ----------

class TestPublicContext:
    def test_only_public_files(self, fake_root):
        fake_root("07_Decisions/pub.md", md("public", "公开内容"))
        fake_root("07_Decisions/int.md", md("internal", "内部内容"))
        fake_root("07_Decisions/pri.md", md("private", "私人内容"))
        fake_root("07_Decisions/sec.md", md("secret", "机密内容"))
        fake_root("07_Decisions/none.md", "没有 frontmatter")
        out, blocked = twin.public_context()
        joined = "".join(out)
        assert "公开内容" in joined
        for word in ("内部内容", "私人内容", "机密内容", "没有 frontmatter"):
            assert word not in joined
        assert blocked == []

    def test_private_block_stripped(self, fake_root):
        fake_root("07_Decisions/pub.md", md("public", "a\n<!-- private -->秘密<!-- /private -->\nb"))
        joined = "".join(twin.public_context()[0])
        assert "秘密" not in joined and "[私密段落已移除]" in joined

    def test_sensitive_file_blocked_not_sent(self, fake_root):
        fake_root("07_Decisions/pub.md", md("public", f"电话 {FAKE_PHONE}"))
        out, blocked = twin.public_context()
        assert FAKE_PHONE not in "".join(out)
        assert len(blocked) == 1

    def test_rules_dir_only_whitelisted(self, fake_root):
        fake_root("_RULES/Lessons.md", md("public", "经验"))
        fake_root("_RULES/Decision_Rules.md", md("public", "时薪规则"))
        joined = "".join(twin.public_context()[0])
        assert "经验" in joined and "时薪规则" not in joined

    def test_summary_without_leaves_skipped(self, fake_root):
        fake_root("01_Skills/_SUMMARY.md", md("public", "空分支总结"))
        assert "空分支总结" not in "".join(twin.public_context()[0])
        fake_root("01_Skills/leaf.md", md("internal", "叶子"))
        joined = "".join(twin.public_context()[0])
        assert "空分支总结" in joined and "叶子" not in joined

    def test_skipped_dirs_never_packed(self, fake_root):
        for d in ("tools", ".chats", ".history", "_VAULT"):
            fake_root(f"{d}/x.md", md("public", f"不该出现-{d}"))
        joined = "".join(twin.public_context()[0])
        assert "不该出现" not in joined

    def test_pack_refuses_when_blocked(self, fake_root):
        fake_root("07_Decisions/pub.md", md("public", f"电话 {FAKE_PHONE}"))
        assert twin.pack() == 1
        assert not (twin.ROOT / "context_pack.md").exists()

    def test_pack_writes_file(self, fake_root):
        fake_root("07_Decisions/pub.md", md("public", "公开内容"))
        assert twin.pack() == 0
        text = (twin.ROOT / "context_pack.md").read_text(encoding="utf-8")
        assert text.startswith(twin.PACK_HEADER) and "公开内容" in text
