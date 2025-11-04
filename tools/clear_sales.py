import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app.db import engine
from app.models import Sale, SaleCancellation

if __name__ == "__main__":
    with Session(engine) as session:
        # Apaga cancelamentos primeiro (evita pendências de referência)
        cancels = session.exec(select(SaleCancellation)).all()
        for c in cancels:
            session.delete(c)
        session.commit()

        vendas = session.exec(select(Sale)).all()
        for v in vendas:
            session.delete(v)
        session.commit()
        print(f"Removidas {len(cancels)} cancelamentos e {len(vendas)} vendas.")
