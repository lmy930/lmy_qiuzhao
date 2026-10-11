import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from broad_sources import ListingParser,archive_pages,article_url,relevant_title,SCHOOLS
from page_evidence import match_scope,evaluate

class BroadSourceTests(unittest.TestCase):
    def test_complete_title_and_encoded_onclick_are_read(self):
        parser=ListingParser()
        parser.feed('<a title="科大讯飞2027届校园招聘" href="/a">科大讯飞...</a><div onclick="windowOpen(&quot;\\/career\\/news\\/view\\/zpgg\\/123&quot;)"><span>三一集团2027届校园招聘</span></div><script><a href="/fake">假信息2027校招</a></script>')
        self.assertEqual(parser.items,[('科大讯飞2027届校园招聘','/a'),('三一集团2027届校园招聘','/career/news/view/zpgg/123')])
    def test_archive_pagination_comes_from_observed_links(self):
        school=SCHOOLS[1]
        pages=archive_pages(school,{'items':[('2','/correcruit/index/p/2.html'),('422','/correcruit/index/p/422.html')]},True)
        self.assertEqual(len(pages),119)
        self.assertEqual(len(archive_pages(school,{'items':[]},True)),0)
        self.assertEqual(len(archive_pages(school,{'items':[('422','/correcruit/index/p/422.html')]},False)),11)
    def test_external_and_meeting_links_are_not_article_evidence(self):
        school=SCHOOLS[1]
        self.assertIsNone(article_url(school,'https://[broken',school['url']))
        self.assertIsNone(article_url(school,'https://evil.test/correcruit/content/id/1.html',school['url']))
        self.assertIsNone(article_url(school,'/recruitment/content/type/2/id/123.html',school['url']))
        self.assertEqual(article_url(school,'/correcruit/content/id/123.html',school['url']),'https://career.hebut.edu.cn/correcruit/content/id/123.html')
    def test_old_cohort_and_internship_are_excluded(self):
        self.assertTrue(relevant_title('科大讯飞2027届秋季校园招聘'))
        for title in ['科大讯飞2026届秋季校园招聘','科大讯飞2027届日常实习生招聘','科大讯飞2027届校招预告','科大讯飞2027届校园招聘取消']:
            self.assertFalse(relevant_title(title))
    def test_brand_and_group_affiliation_are_not_confused(self):
        self.assertEqual(match_scope('美的集团股份有限公司','美的2027届校园招聘'),'employer')
        self.assertEqual(match_scope('中国长江三峡集团有限公司','中国三峡新能源2027届校园招聘'),'subsidiary')
        self.assertEqual(match_scope('三一集团有限公司','三一重工2027届校园招聘'),'subsidiary')
        self.assertIsNone(match_scope('大华 (集团)有限公司','大华股份2027届校园招聘'))
    def test_consumer_brands_and_holding_subsidiaries(self):
        self.assertEqual(match_scope('北京嘀嘀无限科技发展有限公司 (滴滴出行)','滴滴出行2027届校园招聘'),'employer')
        self.assertEqual(match_scope('北京快手科技有限公司','快手2027届校园招聘'),'employer')
        self.assertEqual(match_scope('盛虹控股集团有限公司','东方盛虹2027届校园招聘'),'subsidiary')
        self.assertEqual(match_scope('浙江卫星控股股份有限公司','卫星化学2027届校园招聘'),'subsidiary')
    def test_title_without_recruitment_body_is_not_confirmation(self):
        title='科大讯飞2027届校园招聘'
        self.assertEqual(evaluate('科大讯飞股份有限公司',title,title)['reason'],'recruitment_body_missing')
        self.assertTrue(evaluate('科大讯飞股份有限公司',title,'招聘对象：2027届本科毕业生，简历投递已开启。')['accepted'])
    def test_structured_article_title_and_main_body_are_extracted(self):
        from page_evidence import page_text
        title,text=page_text('<title>大学就业网</title><h4 class="tit">天合光能2027届校园招聘</h4><div id="vsb_content_4_1009_u171"><p>招聘对象：2027届本科生，在线投递简历。</p></div><aside>别的公司2026届校招</aside>')
        self.assertIn('天合光能2027届',title)
        self.assertNotIn('2026届',text)
        self.assertTrue(evaluate('天合光能股份有限公司',title,text)['accepted'])
    def test_explicit_child_affiliation_is_preserved(self):
        title='中冶武勘2027届校园招聘'
        body='公司简介：中冶武勘工程技术有限公司（简称中冶武勘），是中国五矿骨干子企业。招聘对象为2027届本科生，请投递简历。'
        evidence=evaluate('中国五矿集团有限公司',title,body)
        self.assertTrue(evidence['accepted'])
        self.assertEqual(evidence['scope'],'subsidiary')
        customer='公司简介：中冶武勘工程技术有限公司（简称中冶武勘），服务客户中国五矿旗下子企业。招聘对象为2027届本科生，请投递简历。'
        self.assertFalse(evaluate('中国五矿集团有限公司',title,customer)['accepted'])
    def test_declared_brand_binds_only_legal_employer(self):
        body='公司简介：山东豪迈机械科技股份有限公司（简称“豪迈”），成立于1995年。招聘对象2027届本科生，请投递简历。'
        evidence=evaluate('山东豪迈机械科技股份有限公司','豪迈2027届校园招聘',body)
        self.assertTrue(evidence['accepted'])
        self.assertIn('identity_evidence',evidence)
        customer=body.replace('山东豪迈机械科技股份有限公司','服务客户山东豪迈机械科技股份有限公司')
        self.assertFalse(evaluate('山东豪迈机械科技股份有限公司','豪迈2027届校园招聘',customer)['accepted'])
    def test_named_member_is_not_group_wide_launch(self):
        self.assertEqual(match_scope('中国建材集团有限公司','中国建材天山材料股份有限公司2027届校园招聘'),'subsidiary')
        self.assertEqual(match_scope('美的集团股份有限公司','美的集团股份有限公司2027届校园招聘'),'employer')
    def test_operating_entity_introduction_keeps_holding_scope_separate(self):
        text='【企业简介】宁波金田铜业（集团）股份有限公司，招聘对象2027届本科生，简历投递已启动。'
        result=evaluate('宁波金田投资控股有限公司','金田集团2027届校园招聘',text)
        self.assertTrue(result['accepted'])
        self.assertEqual(result['scope'],'subsidiary')
        self.assertIn('scope_evidence',result)
        customer=text.replace('宁波金田铜业','服务客户宁波金田铜业')
        self.assertEqual(evaluate('宁波金田投资控股有限公司','金田集团2027届校园招聘',customer)['scope'],'employer')
    def test_explicit_article_cohort_applies_to_its_job_table(self):
        result=evaluate('骆驼集团股份有限公司','骆驼集团股份有限公司2027届校园招聘','招聘岗位：产品研发工程师。学历本科，专业机械。简历投递邮箱在公司招聘系统。')
        self.assertTrue(result['accepted'])
        self.assertIsNone(result['opening'])
        self.assertFalse(evaluate('骆驼集团股份有限公司','骆驼集团股份有限公司2027届校园招聘','招聘对象：2026届毕业生')['accepted'])
if __name__=='__main__':unittest.main()
