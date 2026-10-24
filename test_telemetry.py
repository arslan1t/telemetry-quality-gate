import json,subprocess,sys,tempfile,unittest
from html.parser import HTMLParser
from pathlib import Path
from telemetry import ISSUE_LABELS,audit,read_csv,render_html

ROOT = Path(__file__).resolve().parent

def row(t,v=20,s='motor'):return dict(timestamp=t,value=v,sensor=s)
class TelemetryTests(unittest.TestCase):
    def test_clean_interleaved_streams(self):
        self.assertTrue(audit([row(0),row(0,s='battery'),row(1),row(1,s='battery')])['passed'])
    def test_all_issue_types(self):
        report=audit([row(0),row(0),row(5,130),row(4),row('bad'),row(6,s='')])
        self.assertEqual(report['issue_counts'],dict(duplicate_timestamp=1,sampling_gap=1,out_of_range=1,out_of_order=1,invalid_number=1,missing_sensor=1))
    def test_late_arrival_does_not_create_false_gap(self):
        report=audit([row(10),row(1),row(11)])
        self.assertEqual(report['issue_counts'],{'out_of_order':1})
    def test_nonfinite_numbers(self):
        for value in ('nan','inf','-inf'):
            self.assertEqual(audit([row(0,value)])['issue_counts'],{'invalid_number':1})
    def test_boundary_values(self):
        self.assertTrue(audit([row(0,-40),row(2,125)])['passed'])
    def test_invalid_configuration(self):
        for config in ({'max_gap':0},{'minimum':200},{'maximum':float('nan')}):
            with self.assertRaises(ValueError):audit([],**config)
    def test_csv_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'input.csv';path.write_text('time,value\n0,1\n')
            with self.assertRaises(ValueError):read_csv(path)

class ReportTests(unittest.TestCase):
    def test_synthetic_fixtures_have_known_counts(self):
        valid=audit(read_csv(ROOT/'example_valid.csv'))
        self.assertEqual((valid['rows'],valid['sensors'],valid['issues']),(8,2,[]))
        invalid=audit(read_csv(ROOT/'example_anomalies.csv'))
        self.assertEqual((invalid['rows'],invalid['sensors'],invalid['passed']),(8,2,False))
        self.assertEqual(invalid['issue_counts'],{kind:1 for kind in ISSUE_LABELS})
        # The range violation and sampling gap refer to the same record.
        self.assertEqual(len({item['line'] for item in invalid['issues']}),5)

    def test_html_has_exact_summary_and_issue_details(self):
        report=audit(read_csv(ROOT/'example_anomalies.csv'))
        page=render_html(report,'synthetic.csv',-40,125,2)
        self.assertIn('<strong>8</strong><span>Rows checked</span>',page)
        self.assertIn('<strong>2</strong><span>Sensors with numeric samples</span>',page)
        self.assertIn('<strong>5</strong><span>Rows with issues</span>',page)
        self.assertIn('<strong>6</strong><span>Total issues</span>',page)
        self.assertIn('<td class="number">4</td><td>motor_temp</td>',page)
        self.assertIn('{&quot;seconds&quot;: 5.0}',page)
        self.assertIn('{&quot;value&quot;: 160.0}',page)
        for label in ISSUE_LABELS.values():
            self.assertIn('<td>'+label+'</td><td class="number">1</td>',page)

    def test_untrusted_source_and_sensor_are_html_escaped(self):
        sensor='<img src=x onerror="alert(1)"> & motor'
        source='</title><script>alert("source")</script>'
        report=audit([row(0,s=sensor),row(0,s=sensor)])
        page=render_html(report,source)
        self.assertIn('&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; motor',page)
        self.assertIn('&lt;/title&gt;&lt;script&gt;',page)
        class TagCollector(HTMLParser):
            def __init__(self):
                super().__init__();self.tags=[]
            def handle_starttag(self,tag,attrs):self.tags.append(tag)
        parser=TagCollector();parser.feed(page)
        self.assertNotIn('script',parser.tags)
        self.assertNotIn('img',parser.tags)

    def test_clean_and_empty_html_explain_scope(self):
        for report in (audit([]),audit([row(0)])):
            with self.subTest(rows=report['rows']):
                page=render_html(report)
                self.assertIn('class="badge PASS">PASS',page)
                self.assertIn('No issues found within the configured checks.',page)
                self.assertIn('Empty inputs pass these checks',page)
                for label in ISSUE_LABELS.values():
                    self.assertIn('<td>'+label+'</td><td class="number">0</td>',page)

class CliTests(unittest.TestCase):
    def run_cli(self,*args):
        return subprocess.run([sys.executable,str(ROOT/'telemetry.py'),*map(str,args)],
                              capture_output=True,text=True,check=False)

    def test_json_and_optional_html_share_result_and_exit_status(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'quality report.html'
            for name,status in (('example_valid.csv',0),('example_anomalies.csv',1)):
                with self.subTest(fixture=name):
                    result=self.run_cli(ROOT/name,'--html-report',output)
                    self.assertEqual(result.returncode,status,result.stderr)
                    self.assertEqual(result.stderr,'')
                    self.assertEqual(json.loads(result.stdout),audit(read_csv(ROOT/name)))
                    self.assertIn('PASS' if status==0 else 'REVIEW',output.read_text())

    def test_default_command_keeps_json_only(self):
        result=self.run_cli(ROOT/'example.csv')
        self.assertEqual(result.returncode,1)
        self.assertEqual(json.loads(result.stdout),audit(read_csv(ROOT/'example.csv')))
        self.assertEqual(result.stderr,'')

    def test_report_must_not_overwrite_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'input.csv'
            original='timestamp,sensor,value\n0,motor,20\n'
            source.write_text(original)
            result=self.run_cli(source,'--html-report',source)
            self.assertEqual(result.returncode,2)
            self.assertEqual(result.stdout,'')
            self.assertIn('must differ from the input CSV',result.stderr)
            self.assertEqual(source.read_text(),original)

    def test_unwritable_report_and_bad_config_use_error_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            for args in (('--html-report',directory),('--max-gap','0')):
                with self.subTest(args=args):
                    result=self.run_cli(ROOT/'example_valid.csv',*args)
                    self.assertEqual(result.returncode,2)
                    self.assertEqual(result.stdout,'')
                    self.assertTrue(result.stderr)
if __name__=='__main__':unittest.main()
