import json
import pathlib
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from source_documents import source_kind, publisher_key, decode_document
from page_evidence import evaluate, page_text, deadline_evidence, opening_evidence
from verify_pages import scan
from update_daily_changes import update_history
NAME='中国农业发展银行'
TITLE=NAME+'2027年度校园招聘公告'
BODY='<p>2027年度校园招聘</p><p>报名时间：2026年9月15日至10月10日</p>'

class DocumentTests(unittest.TestCase):
    def test_article_api_keeps_title_and_content(self):
        raw=json.dumps({'data':{'article':{'title':TITLE,'content':BODY}}})
        document=decode_document(raw,'application/json')
        title,text=page_text(document)
        result=evaluate(NAME,title,text,'2026-10-11')
        self.assertTrue(result['accepted'])
        self.assertEqual(result['opening']['date'],'2026-09-15')
        self.assertEqual(result['deadline']['date'],'2026-10-10')
    def test_unrecognized_json_is_not_recruitment(self):
        with self.assertRaises(ValueError):decode_document('{"message":"login required"}','application/json')
    def test_article_ignores_sidebar_dates(self):
        title,text=page_text('<title>'+TITLE+'</title><article>'+BODY+'<img src="x"/><br>正文结束</article><aside>2026届网申时间：2026年1月1日</aside>')
        self.assertNotIn('2026届',text)
        self.assertIn('正文结束',text)
        self.assertEqual(evaluate(NAME,title,text,'2026-10-11')['opening']['date'],'2026-09-15')
    def test_long_article_application_dates_are_not_truncated(self):
        text='2027届校园招聘'+('公司介绍。'*1500)+'简历投递时间为：2026年9月15日至10月10日'
        self.assertEqual(opening_evidence(text,'2026-10-11',cohort_bound=True)['date'],'2026-09-15')
    def test_secondary_hosts_not_primary(self):
        self.assertEqual(source_kind(NAME,'https://www.fenbi.com/a'),'recruitment')
        self.assertEqual(publisher_key('https://hera-webapp.fenbi.com/a'),'fenbi.com')
        self.assertIsNone(source_kind(NAME,'https://fenbi.com.evil.test/a'))
    def test_deadline_never_comes_from_publication(self):
        self.assertIsNone(deadline_evidence('2027届校招 发布时间：2026年10月10日'))
        self.assertIsNone(deadline_evidence('2026届和2027届招聘 报名截止时间：2026年10月10日'))

class RepostTests(unittest.TestCase):
    def run_scan(self,urls,documents):
        data={'companies':[{'name':NAME,'status':'待核验','open_date':None}]}
        leads={'leads':[{'name':NAME,'hits':[{'url':u} for u in urls]}]}
        with patch('verify_pages.fetch',side_effect=lambda u:(u,documents[u],u)):
            report=scan(data,leads)
        return data['companies'][0],report
    def test_one_repost_is_candidate_not_verified_date(self):
        u='https://www.fenbi.com/a';c,r=self.run_scan([u],{u:'<title>'+TITLE+'</title>'+BODY})
        self.assertEqual(c['status'],'待核验');self.assertIsNone(c['open_date'])
        self.assertEqual(c['opening_date_candidates'][0]['date'],'2026-09-15')
        self.assertEqual(r['accepted_employers'],0)
    def test_same_publisher_subdomains_do_not_corroborate(self):
        urls=['https://www.fenbi.com/a','https://hera-webapp.fenbi.com/b']
        c,r=self.run_scan(urls,{u:'<title>'+TITLE+'</title>'+BODY+str(i) for i,u in enumerate(urls)})
        self.assertIsNone(c['open_date'])
    def test_identical_syndicated_text_does_not_corroborate(self):
        urls=['https://www.fenbi.com/a','https://www.eoffcn.com/b']
        c,r=self.run_scan(urls,{u:'<title>'+TITLE+'</title>'+BODY for u in urls})
        self.assertIsNone(c['open_date'])
    def test_different_publishers_matching_dates(self):
        urls=['https://www.fenbi.com/a','https://www.eoffcn.com/b']
        documents={urls[0]:'<title>'+TITLE+'</title>'+BODY,
                   urls[1]:'<title>'+TITLE+'</title><p>2027届招聘，网上报名时间：2026年9月15日，招聘信息正文。</p>'}
        c,r=self.run_scan(urls,documents)
        self.assertEqual(c['open_date'],'2026-09-15')
        self.assertEqual(c['open_date_evidence']['source_kind'],'corroborated_recruitment')
        self.assertEqual(len(c['open_date_evidence']['corroborating_sources']),2)
    def test_conflicting_reposts_do_not_pick_majority(self):
        urls=['https://www.fenbi.com/a','https://www.eoffcn.com/b']
        c,r=self.run_scan(urls,{u:'<title>'+TITLE+'</title>'+BODY.replace('9月15日','9月'+str(15+i)+'日') for i,u in enumerate(urls)})
        self.assertIsNone(c['open_date'])
    def test_recruitment_page_follows_actual_official_link(self):
        secondary='https://www.fenbi.com/a';primary='https://www.adbc.com.cn/recruitment'
        c,r=self.run_scan([secondary],{secondary:'<title>'+TITLE+'</title>'+BODY+'<a href="'+primary+'">官方报名</a>',primary:'<title>'+TITLE+'</title>'+BODY})
        self.assertEqual(r['pages_attempted'],2)
        self.assertEqual(c['open_date_evidence']['source_kind'],'official')
    def test_legacy_date_is_corrected_but_preserved_for_audit(self):
        data={'companies':[{'name':NAME,'status':'已发布公告（网申待核验）','open_date':'2026-09-14'}]}
        url='https://career.nankai.edu.cn/a'
        with patch('verify_pages.fetch',return_value=(url,'<title>'+TITLE+'</title>'+BODY,'digest')):
            r=scan(data,{'leads':[{'name':NAME,'hits':[{'url':url}]}]})
        c=data['companies'][0]
        self.assertEqual(c['open_date'],'2026-09-15')
        self.assertEqual(c['historical_open_dates'][0]['date'],'2026-09-14')
        self.assertEqual(c['status'],'已结束')

class DailyChangeTests(unittest.TestCase):
    def company(self,date='2026-09-15'):
        return {'name':NAME,'groups':['银行'],'status':'已发布公告（网申待核验）','open_date':date,'open_date_evidence':{'date':date,'scope':'employer','first_verified_at':'2026-10-11T09:00:00+08:00'}}
    def test_initial_baseline_never_marks_everyone_new(self):
        h,new,dates=update_history([self.company()],None,'2026-10-11')
        self.assertEqual(h['events'],[]);self.assertEqual((new,dates),(0,0))
    def test_backfill_is_separate_and_idempotent(self):
        h={'events':[],'known_launch_names':[NAME],'known_open_dates':{}}
        h,new,dates=update_history([self.company()],h,'2026-10-11')
        self.assertEqual((new,dates),(0,1));self.assertEqual(h['events'][0]['kind'],'date_verified')
        self.assertEqual(h['events'][0]['date'],'2026-10-11')
        self.assertEqual(h['events'][0]['opening_date'],'2026-09-15')
        h,new,dates=update_history([self.company()],h,'2026-10-12')
        self.assertEqual((new,dates),(0,0));self.assertEqual(len(h['events']),1)
    def test_rechecking_pages_preserves_first_verification(self):
        c=self.company();c['open_date_evidence']['checked_at']='2026-10-11T09:00:00+08:00'
        url='https://career.nankai.edu.cn/a'
        with patch('verify_pages.fetch',return_value=(url,'<title>'+TITLE+'</title>'+BODY,'digest')):
            scan({'companies':[c]},{'leads':[{'name':NAME,'hits':[{'url':url}]}]})
        self.assertEqual(c['open_date_evidence']['first_verified_at'],'2026-10-11T09:00:00+08:00')

class ScopeAndCopyTests(unittest.TestCase):
    def test_subsidiary_dates_are_not_group_dates(self):
        from page_evidence import match_scope
        self.assertEqual(match_scope('TCL科技集团股份有限公司','TCL华星2027校园招聘'),'subsidiary')
        self.assertEqual(match_scope('中国航空集团有限公司','中国国航2027校园招聘'),'subsidiary')
        self.assertEqual(match_scope('中国建设银行股份有限公司','中国建设银行上海支行2027校园招聘'),'subsidiary')
    def test_minor_edits_do_not_make_reposts_independent(self):
        urls=['https://www.fenbi.com/a','https://www.eoffcn.com/b']
        body=BODY+('招聘岗位、应聘条件、企业介绍和校园招聘流程。'*30)
        c,r=RepostTests().run_scan(urls,{u:'<title>'+TITLE+'</title><article>'+body+('整理发布' if i else '')+'</article>' for i,u in enumerate(urls)})
        self.assertIsNone(c['open_date'])

class ApplicationChannelTests(unittest.TestCase):
    def test_only_article_application_route_is_bound(self):
        from source_documents import application_links,source_kind
        html='<nav><a href="https://other.zhiye.com/">别的公司</a></nav><article><p>网申地址：</p><a href="https://example.zhiye.com/campus">点击投递</a></article>'
        rows=application_links(html,'https://career.nankai.edu.cn/a')
        self.assertEqual(len(rows),1)
        record={**rows[0],'company':'美的集团股份有限公司','proof_url':'https://career.nankai.edu.cn/a','proof_sha256':'a'*64}
        self.assertEqual(source_kind('美的集团股份有限公司','https://example.zhiye.com/jobs',[record]),'official_application')
        self.assertIsNone(source_kind('美的集团股份有限公司','https://other.zhiye.com/jobs',[record]))
        self.assertIsNone(source_kind('科大讯飞股份有限公司','https://example.zhiye.com/jobs',[record]))
    def test_shared_platform_is_tenant_bound(self):
        from source_documents import application_links,source_kind
        rows=application_links('<article><a href="https://app.mokahr.com/campus_apply/testcorp/123/">网申</a></article>','https://career.nankai.edu.cn/a')
        record={**rows[0],'company':'美的集团股份有限公司','proof_url':'https://career.nankai.edu.cn/a','proof_sha256':'a'*64}
        self.assertEqual(source_kind('美的集团股份有限公司','https://app.mokahr.com/campus_apply/testcorp/123/jobs',[record]),'official_application')
        self.assertIsNone(source_kind('美的集团股份有限公司','https://app.mokahr.com/campus_apply/testcorp/1234/jobs',[record]))
    def test_article_cohort_is_not_granted_to_unrelated_application_source(self):
        from source_documents import source_kind
        record={'company':'美的集团股份有限公司','url':'https://example.zhiye.com/','url_prefix':'https://example.zhiye.com/','proof_url':'https://untrusted.test/article','proof_sha256':'a'*64}
        self.assertIsNone(source_kind('美的集团股份有限公司','https://example.zhiye.com/jobs',[record]))

class StructuredSchoolArticleTests(unittest.TestCase):
    def test_anonymous_article_json_decodes_actual_body(self):
        from source_documents import decode_document
        from page_evidence import page_text,evaluate
        import json
        raw=json.dumps({'code':200,'data':{'zpzt':'华勤技术2027届校招','zpxxEditor':'<p>招聘对象：2027届本科生，请投递简历。</p>','dwjs':'公司简介：华勤技术股份有限公司。'}})
        title,text=page_text(decode_document(raw,'application/json'))
        self.assertIn('华勤技术2027届',title)
        self.assertTrue(evaluate('华勤技术股份有限公司',title,text)['accepted'])
    def test_article_fetch_uses_observed_public_endpoint(self):
        from unittest.mock import patch
        from verify_pages import fetch
        import io,json
        class Response(io.BytesIO):
            def __init__(self,body,url,content_type):
                super().__init__(body);self.url=url
                from email.message import Message
                self.headers=Message();self.headers['Content-Type']=content_type
            def geturl(self):return self.url
        url='https://jiuye.swjtu.edu.cn/career/zpxx/view/zpxx/123'
        shell=b'<script>postAjax("/zpxx/data/zpxx/" + id)</script>'
        payload=json.dumps({'code':200,'data':{'zpzt':'华勤技术2027届校招','zpxxEditor':'招聘对象2027届本科生，投递简历。'}},ensure_ascii=False).encode()
        with patch('verify_pages.urllib.request.urlopen',side_effect=[Response(shell,url,'text/html'),Response(payload,url,'application/json')]) as requests:
            final,document,digest=fetch(url)
        self.assertEqual(final,url)
        self.assertEqual(requests.call_args_list[1].args[0].full_url,'https://jiuye.swjtu.edu.cn/career/zpxx/data/zpxx/123')
        self.assertIn('投递简历',document)
        import hashlib
        self.assertEqual(digest,hashlib.sha256(payload).hexdigest())

class MalformedPublicLinkTests(unittest.TestCase):
    def test_bad_links_do_not_abort_the_whole_scan(self):
        from source_documents import application_links,source_kind
        self.assertIsNone(source_kind('美的集团股份有限公司','https://[broken'))
        self.assertEqual(application_links('<article>网申：https://[broken</article>','https://career.nankai.edu.cn/a'),[])
