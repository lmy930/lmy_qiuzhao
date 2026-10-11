import sys
import pathlib
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from page_evidence import opening_evidence, evaluate, match_scope, page_text
from verify_pages import trusted

class EvidenceTests(unittest.TestCase):
    def test_explicit_application_date(self):
        e=opening_evidence('某企业2027届校园招聘\n网申时间：2026年9月3日至2026年10月9日','2026-10-11')
        self.assertEqual(e['date'],'2026-09-03')
        self.assertIn('网申',e['quote'])
    def test_publication_and_discovery_are_not_opening(self):
        for text in ['2027届校园招聘 发布时间：2026年9月3日','2027届校园招聘 发现时间：2026年9月3日','2027届校园招聘 截止日期：2026年10月9日','2027届校园招聘 即日起报名']:
            self.assertIsNone(opening_evidence(text,'2026-10-11'))
    def test_date_before_start(self):
        self.assertEqual(opening_evidence('2027届校招 2026年9月3日起接受网上报名','2026-10-11')['date'],'2026-09-03')
    def test_invalid_future_ambiguous_dates(self):
        for text in ['2027届 网申时间：2026年2月30日','2027届 网申时间：2026年12月1日','2027届 网申时间：2026年9月1日；报名时间：2026年9月2日','2026届和2027届 网申时间：2026年9月1日']:
            self.assertIsNone(opening_evidence(text,'2026-10-11'))
    def test_subsidiary_scope(self):
        self.assertEqual(match_scope('中国航天科工集团有限公司','中国航天科工二院二十三所2027届校园招聘'),'subsidiary')
        self.assertEqual(match_scope('中国建设银行股份有限公司','中国建设银行上海分行2027校园招聘'),'subsidiary')
    def test_shared_tcl_brand(self):
        self.assertIsNone(match_scope('TCL科技集团股份有限公司','TCL2027校园招聘'))
        self.assertIsNone(match_scope('TCL 实业控股股份有限公司','TCL华星2027校园招聘'))
    def test_false_host_trust(self):
        self.assertFalse(trusted('中国银行股份有限公司','https://bankofchina.com.evil.test/2027'))
        self.assertFalse(trusted('中国银行股份有限公司','https://fake-edu.cn/'))
        self.assertTrue(trusted('中国银行股份有限公司','https://www.bankofchina.com/'))
    def test_sidebar_cohort_does_not_qualify(self):
        self.assertFalse(evaluate('中国银行股份有限公司','中国银行2026届校园招聘','相关链接2027届校园招聘')['accepted'])
    def test_html_ignores_script(self):
        title,text=page_text('<title>中国银行2027校园招聘</title><script>网申时间：2026年1月1日</script><p>网申时间：2026年9月3日</p>')
        self.assertNotIn('1月1日',text)
        self.assertEqual(opening_evidence(text,'2026-10-11')['date'],'2026-09-03')

class PipelineTests(unittest.TestCase):
    def test_scan_backfills_unknown_date_and_keeps_subsidiary_separate(self):
        from unittest.mock import patch
        from verify_pages import scan
        data={'companies':[
            {'name':'中国农业发展银行','status':'已发布公告（网申待核验）','open_date':None},
            {'name':'中国建设银行股份有限公司','status':'待核验','open_date':None}]}
        leads={'leads':[
            {'name':'中国农业发展银行','hits':[{'url':'https://career.nankai.edu.cn/a','title':'不使用搜索标题替代正文'}]},
            {'name':'中国建设银行股份有限公司','hits':[{'url':'https://career.nankai.edu.cn/b','title':''}]}]}
        def fetch(url):
            title='中国农业发展银行2027年度校园招聘' if url.endswith('a') else '中国建设银行上海分行2027年度校园招聘'
            return url,'<title>'+title+'</title><p>报名时间：2026年9月15日</p>','digest'
        with patch('verify_pages.fetch',fetch):report=scan(data,leads)
        self.assertEqual(data['companies'][0]['open_date'],'2026-09-15')
        self.assertIsNone(data['companies'][1]['open_date'])
        self.assertEqual(data['companies'][1]['source_scope'],'subsidiary')
        self.assertEqual(len(data['companies'][1]['subsidiary_openings']),1)
        self.assertEqual(report['new_open_dates'],['中国农业发展银行'])
    def test_fetch_failure_does_not_erase_prior_evidence(self):
        from unittest.mock import patch
        from verify_pages import scan
        data={'companies':[{'name':'中国农业发展银行','status':'已发布公告（网申待核验）','open_date':'2026-09-15'}]}
        leads={'leads':[{'name':'中国农业发展银行','hits':[{'url':'https://career.nankai.edu.cn/a'}]}]}
        with patch('verify_pages.fetch',side_effect=OSError('blocked')):r=scan(data,leads)
        self.assertEqual(r['pages_read'],0)
        self.assertEqual(data['companies'][0]['open_date'],'2026-09-15')
    def test_conflicting_dates_are_reported_not_overwritten(self):
        from unittest.mock import patch
        from verify_pages import scan
        data={'companies':[{'name':'中国农业发展银行','status':'已发布公告（网申待核验）','open_date':'2026-09-14'}]}
        leads={'leads':[{'name':'中国农业发展银行','hits':[{'url':'https://career.nankai.edu.cn/a'}]}]}
        with patch('verify_pages.fetch',return_value=('https://career.nankai.edu.cn/a','<title>中国农业发展银行2027届校园招聘</title><p>网申时间：2026年9月15日</p>','digest')):r=scan(data,leads)
        self.assertEqual(data['companies'][0]['open_date'],'2026-09-14')
        self.assertEqual(r['checks'][0]['date_conflict'],'2026-09-14')

class ObservedEvidenceTests(unittest.TestCase):
    def test_real_scan_date_excerpts(self):
        import json
        path=pathlib.Path(__file__).resolve().parents[1]/'data/page_verification_success_report.json'
        records=json.loads(path.read_text())['retained_checks']
        for record in records:
            if not record['opening']:continue
            with self.subTest(company=record['company']):
                result=opening_evidence(record['title']+'\n'+record['opening']['quote'],'2026-10-11')
                self.assertEqual(result['date'],record['opening']['date'])
                self.assertEqual(len(record['sha256']),64)
    def test_search_publisher_labels_cannot_establish_trust(self):
        from promote_evidence import score
        h={'title':'阿里巴巴2027届校园招聘 - 大学就业指导中心','url':'https://example.test/','evidence_level':'university_listing'}
        self.assertEqual(score('阿里巴巴 (中国)有限公司',h),1)

class DiscoveryTests(unittest.TestCase):
    def test_known_launch_without_date_uses_backfill_query(self):
        from unittest.mock import patch
        from discover import worker
        with patch('discover.feed',return_value=[]) as feed, patch('discover.google_news',return_value=[]), patch('discover.site_feed',return_value=[]):
            result=worker({'name':'中国农业发展银行','status':'已发布公告（网申待核验）'})
        self.assertTrue(feed.call_args.args[2])
        self.assertIsNone(result[2])
    def test_partial_provider_failure_is_not_hidden(self):
        from unittest.mock import patch
        from discover import worker
        with patch('discover.feed',side_effect=OSError('blocked')), patch('discover.google_news',return_value=[]), patch('discover.site_feed',return_value=[]):
            result=worker({'name':'中国农业发展银行','status':'待核验'})
        self.assertIsNone(result[2])
        self.assertEqual(result[3],['blocked'])
