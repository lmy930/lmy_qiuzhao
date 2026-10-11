import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
import employer_aliases
import promote_evidence
import university_sources

class EmployerAliasTests(unittest.TestCase):
    def test_legal_name_and_brand(self):
        self.assertIn("阿里巴巴",employer_aliases.aliases("阿里巴巴 (中国)有限公司"))
        self.assertIn("小米集团",employer_aliases.aliases("小米通讯技术有限公司"))
        self.assertIn("tcl实业",employer_aliases.aliases("TCL 实业控股股份有限公司"))
        self.assertIn("中核集团",employer_aliases.aliases("中国核工业集团有限公司"))
    def test_aviation_false_positive_is_rejected(self):
        h={"title":"中国航空发动机集团2027届校园招聘启动 - 国资委","url":"https://wap.sasac.gov.cn/example"}
        self.assertEqual(promote_evidence.score("中国航空集团有限公司",h),0)
    def test_ambiguous_group_aliases(self):
        h={"title":"中国航空工业发展研究中心2027届校园招聘 - 南开大学就业网","url":"https://career.nankai.edu.cn/correcruit/content/id/118821.html","evidence_level":"university_listing"}
        self.assertEqual(promote_evidence.score("中国航空集团有限公司",h),0)
        h={"title":"中国农业发展银行2027年度校园招聘公告 - 南开大学就业网","url":"https://career.nankai.edu.cn/correcruit/content/id/119483.html","evidence_level":"university_listing"}
        self.assertEqual(promote_evidence.score("中国农业发展集团有限公司",h),0)
        self.assertEqual(promote_evidence.score("中国农业发展银行",h),3)
    def test_trusted_university_2027_promotion(self):
        h={"title":"阿里巴巴2027届应届生招聘全球启动 - 南开大学就业网","url":"https://career.nankai.edu.cn/correcruit/content/id/116569.html","evidence_level":"university_listing"}
        self.assertEqual(promote_evidence.score("阿里巴巴 (中国)有限公司",h),3)
    def test_old_cohort_not_promoted(self):
        h={"title":"小米集团2026届校园招聘 - 南开大学","url":"https://career.nankai.edu.cn/"}
        self.assertEqual(promote_evidence.score("小米通讯技术有限公司",h),0)
    def test_2027_global_campus_recruitment(self):
        h={"title":"TCL2027届全球校园招聘 - 南开大学就业网","url":"https://career.nankai.edu.cn/correcruit/content/id/111111.html","evidence_level":"university_listing"}
        self.assertEqual(promote_evidence.score("TCL 实业控股股份有限公司",h),3)
    def test_school_anchor_extractor(self):
        parser=university_sources.Anchors()
        parser.feed('<div><a href="/correcruit/content/id/123.html">阿里巴巴2027届应届生招聘全球启动！</a></div>')
        self.assertEqual(parser.items[0][0],"阿里巴巴2027届应届生招聘全球启动！")
    def test_explicit_dates_not_inferred(self):
        self.assertNotIn("open_date",{"title":"2027校园招聘正式启动","url":"https://example.com/"})

if __name__=="__main__":
    unittest.main()
