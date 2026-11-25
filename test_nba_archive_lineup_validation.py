import csv
import io
import unittest
from nba_archive_lineup_validation import validate_archived_lineups

class ArchivedNBAValidationTests(unittest.TestCase):
    def setUp(self):
        self.pool = []
        self.lineup = []
        slots = ['PG','SG','SF','PF','C','G/F','F/C','UTIL','UTIL']
        for i, slot in enumerate(slots):
            p = {'id': f'137037-{i}', 'player': f'P{i}', 'salary': '5000',
                 'positions': slot+'/UTIL' if slot != 'UTIL' else 'PG/UTIL',
                 'status': '', 'consensus_scenario_fd': '20'}
            self.pool.append(p)
            self.lineup.append({'lineup':'1','slot':slot,'player_id':p['id'],
                                'player':p['player'],'salary':'5000','scenario_fd':'20'})
    def csv(self, rows):
        output=io.StringIO()
        writer=csv.DictWriter(output,fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()
    def check(self):
        return validate_archived_lineups(self.csv(self.pool),self.csv(self.lineup))
    def test_valid(self):
        self.assertEqual(self.check()['lineups'][0]['scenario_fd'],180)
    def test_duplicate(self):
        self.lineup[0]['player_id']=self.lineup[1]['player_id']
        with self.assertRaises(ValueError): self.check()
    def test_wrong_slot(self):
        self.lineup[0]['slot']='PF'
        with self.assertRaises(ValueError): self.check()
    def test_projection_mismatch(self):
        self.lineup[0]['scenario_fd']='21'
        with self.assertRaises(ValueError): self.check()
    def test_out(self):
        self.pool[0]['status']='OUT'
        with self.assertRaises(ValueError): self.check()
    def test_missing_id(self):
        self.lineup[0]['player_id']='137037-999'
        with self.assertRaises(ValueError): self.check()

if __name__ == '__main__':
    unittest.main()
