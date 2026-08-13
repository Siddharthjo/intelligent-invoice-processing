from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from invoice_processing.persistence.db import get_session

SessionDep = Annotated[Session, Depends(get_session)]
