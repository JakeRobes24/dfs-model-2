import unittest
from nba_minutes_sensitivity import sensitivity

class TestSensitivity(unittest.TestCase):
    def test_crossing(self):
        p='id,consensus_scenario_minutes,consensus_scenario_fd\n1,28,28\n2,20,20\n'
        l='lineup,player_id,scenario_fd\n1,2,30\n2,1,28\n'
        rows=sensitivity(p,l,'1',[28,31])
        self.assertEqual(rows[0]['ranked'][0],'1')
        self.assertEqual(rows[1]['ranked'][0],'2')
    def test_missing_id(self):
        with self.assertRaises(KeyError):
            sensitivity('id,consensus_scenario_minutes,consensus_scenario_fd\n1,28,28\n','lineup,player_id,scenario_fd\n1,1,28\n','x',[28])
    def test_zero_minutes(self):
        with self.assertRaises(ValueError):
            sensitivity('id,consensus_scenario_minutes,consensus_scenario_fd\n1,0,28\n','lineup,player_id,scenario_fd\n1,1,28\n','1',[28])
if __name__=='__main__':unittest.main()
