import tempfile,unittest
from pathlib import Path
from telemetry import audit,read_csv

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
if __name__=='__main__':unittest.main()
