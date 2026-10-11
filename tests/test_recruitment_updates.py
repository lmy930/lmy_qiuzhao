import io,json,pathlib,sys,unittest,urllib.parse
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from update_daily_changes import update_history
from discover import site_feed
from aggregate_sources import inspect

class UpdateTests(unittest.TestCase):
    def test_repeated_scan_and_body_hash_do_not_create_daily_updates(self):
        c={'name':'企业','status':'已开启','page_verification':{'url':'https://example.com/a','sha256':'first'}}
        h,_,_=update_history([c],None,'2026-10-11')
        c['last_checked']='2026-10-12';c['page_verification']['sha256']='dynamic-rendering'
        h,_,_=update_history([c],h,'2026-10-12');self.assertEqual(h['events'],[])
        c['status']='已结束';h,_,_=update_history([c],h,'2026-10-12')
        self.assertEqual(h['events'][0]['changed_fields'],['status'])
        h,_,_=update_history([c],h,'2026-10-12');self.assertEqual(len(h['events']),1)
    def test_official_failure_still_queries_other_platform(self):
        requested=[]
        def fetch(req,timeout):
            query=urllib.parse.parse_qs(urllib.parse.urlsplit(req.full_url).query)['q'][0];requested.append(query)
            if 'site:huawei.com' in query:raise OSError('official unavailable')
            return io.BytesIO(b'<rss><channel/></rss>')
        with patch('discover.urllib.request.urlopen',side_effect=fetch),patch('discover.SOURCES',[{'domain':'nowcoder.com','name':'fallback','groups':['民营500']}]):
            self.assertEqual(site_feed({'name':'华为投资控股有限公司','groups':['民营500']}),[])
        self.assertEqual(len(requested),2);self.assertTrue(any('site:nowcoder.com' in q for q in requested))
    def test_platform_preserves_article_link_without_confirming_status(self):
        c={'name':'华为投资控股有限公司'}
        matches,_=inspect(('https://www.nowcoder.com/',{'text':'','links':[('华为2027届校园招聘','/article/123')]},None),[c])
        self.assertEqual(matches[0]['hit']['url'],'https://www.nowcoder.com/article/123')
        self.assertEqual(matches[0]['hit']['evidence_level'],'article_link')
