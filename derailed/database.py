"""
Copyright (C) 2021-2023 Derailed.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import os
from inspect import isbuiltin, isfunction, ismethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine = create_async_engine(
    os.environ['PG_URI'],
    future=True,
)


AsyncSessionFactory = async_sessionmaker(engine, autoflush=True, expire_on_commit=False)


async def uses_db():
    session = AsyncSessionFactory()
    try:
        yield session
    except:
        await session.rollback()
    finally:
        await session.close()


def get_db() -> AsyncSession:
    session: AsyncSession = AsyncSessionFactory()
    return session


def to_dict(self) -> dict[str, Any]:
    d = {}
    for k in dir(self):
        if k == '__dict__':
            continue

        attr = getattr(self, k)

        if (
            not isfunction(attr)
            and k not in ['registry', 'mro', 'metadata']
            and not k.startswith('_')
            and not ismethod(attr)
            and not isbuiltin(attr)
        ):
            d[k] = attr
    return d
