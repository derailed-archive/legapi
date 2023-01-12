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
from dotenv import load_dotenv
from fastapi import FastAPI, Request

load_dotenv()

from .powerbase import rate_limiter

# routers
from .routers import user
from .routers.channels import guild_channel, message
from .routers.guilds import guild_information, guild_management

app = FastAPI(version='1')
app.state.limiter = rate_limiter
app.include_router(user.router)
app.include_router(guild_information.router)
app.include_router(guild_management.router)
app.include_router(guild_channel.router)
app.include_router(message.router)


@app.get('/')
async def index(request: Request) -> str:
    return 'hello!'
