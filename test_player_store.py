import tempfile
import unittest
from pathlib import Path
import pandas as pd
from player_store import connect,import_snapshot,import_actuals,audit_summary

class TestPlayerStore(unittest.TestCase):
    def test_import_idempotency_new_players_and_actuals(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td); db=connect(p/'history.sqlite')
            def write(rows):
                f=p/'research.csv';pd.DataFrame(rows).to_csv(f,index=False);return f
            a={'fanduel_id':'contest-11','fanduel_name':'Player A','salary':5000,'position':'PG','roster_eligibility':'PG','adjusted_fd_points':30,'adjusted_minutes':30}
            b={**a,'fanduel_id':'contest-12','fanduel_name':'Player B','salary':6000}
            r=import_snapshot(db,write([a,b]),'2026-11-20',2)
            self.assertEqual(r['new_players'],2)
            self.assertEqual(import_snapshot(db,p/'research.csv','2026-11-20')['status'],'already_imported')
            c={**a,'fanduel_id':'contest-13','fanduel_name':'Player C'}
            self.assertEqual(import_snapshot(db,write([a,c]),'2026-11-21')['new_players'],1)
            actual=p/'actuals.csv';pd.DataFrame([{'fanduel_id':'contest-11','actual_minutes':25,'actual_fd_points':20},{'fanduel_id':'contest-12','actual_minutes':None,'actual_fd_points':None}]).to_csv(actual,index=False)
            self.assertEqual(import_actuals(db,actual,'2026-11-20')['recorded'],1)
            self.assertEqual(audit_summary(db,'2026-11-20'),(2,1,1))
            pd.DataFrame([{'fanduel_id':'contest-11','actual_minutes':26,'actual_fd_points':20}]).to_csv(actual,index=False)
            with self.assertRaises(ValueError):import_actuals(db,actual,'2026-11-20')
            db.close()
    def test_slate_membership_and_idempotent_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td); db=connect(p/'history.sqlite')
            research=p/'research.csv'; actual=p/'actual.csv'
            base=dict(fanduel_name='A',salary=5000,position='PG',roster_eligibility='PG',adjusted_fd_points=25)
            for day,ids in [('2026-11-20',['c-1','c-2']),('2026-11-21',['c-3'])]:
                pd.DataFrame([dict(base,fanduel_id=i) for i in ids]).to_csv(research,index=False)
                import_snapshot(db,research,day)
            row=dict(fanduel_id='c-1',actual_minutes=30,actual_fd_points=25,actuals_source='first evidence')
            pd.DataFrame([row]).to_csv(actual,index=False)
            import_actuals(db,actual,'2026-11-20')
            original=db.execute('SELECT * FROM actuals').fetchall()
            pd.DataFrame([dict(row,actuals_source='retry evidence')]).to_csv(actual,index=False)
            self.assertEqual(import_actuals(db,actual,'2026-11-20')['unchanged'],1)
            self.assertEqual(db.execute('SELECT * FROM actuals').fetchall(),original)
            pd.DataFrame([dict(row,fanduel_id='c-2'),dict(row,fanduel_id='c-3')]).to_csv(actual,index=False)
            with self.assertRaisesRegex(ValueError,'this slate'):
                import_actuals(db,actual,'2026-11-20')
            self.assertEqual(db.execute('SELECT * FROM actuals').fetchall(),original)
            for col,val in [('actual_minutes',-1),('actual_minutes',float('inf')),('actual_fd_points',float('-inf'))]:
                pd.DataFrame([dict(row,**{col:val})]).to_csv(actual,index=False)
                with self.assertRaisesRegex(ValueError,'Invalid actual numeric'):
                    import_actuals(db,actual,'2026-11-20',allow_overwrite=True)
            self.assertEqual(db.execute('SELECT * FROM actuals').fetchall(),original)
            db.close()

if __name__=='__main__':unittest.main()
