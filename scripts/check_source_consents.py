"""Read-only check: supplied workbook consent rows vs the imported SQLite snapshot."""
import json
import sqlite3
import sys
from pathlib import Path
import openpyxl

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.ingestion import serial


def compare(workbook,database):
    wb=openpyxl.load_workbook(workbook,read_only=True,data_only=True)
    try:
        rows=iter(wb['consent_status'].values);headers=next(rows)
        expected=[{k:serial(v) for k,v in zip(headers,row) if k} for row in rows]
    finally:wb.close()
    connection=sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)
    try:
        actual=[json.loads(r[0]) for r in connection.execute("SELECT payload FROM source_records WHERE source='consent_status' ORDER BY id")]
    finally:connection.close()
    canonical=lambda rows:sorted(json.dumps(row,sort_keys=True,ensure_ascii=False) for row in rows)
    return {'workbook_rows':len(expected),'database_rows':len(actual),'equal':canonical(expected)==canonical(actual)}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook',type=Path,default=ROOT/'data/maingau_nba_mockdata.xlsx')
    parser.add_argument('--database',type=Path,default=ROOT/'data/nba.sqlite')
    args=parser.parse_args();result=compare(args.workbook,args.database)
    print(json.dumps(result,indent=2));raise SystemExit(0 if result['equal'] else 1)
