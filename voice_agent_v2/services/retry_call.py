from fastapi import FastAPI, Request
import asyncio
import subprocess
import json

app = FastAPI()

@app.post("/retry_call")
async def retry_call(request: Request):
    data = await request.json()
    dial_info = data["dial_info"]
    delay = int(data["delay"])
    print(dial_info)

    async def launch_job():
        await asyncio.sleep(delay)

        # Crea nuevo job con metadata
        '''
        cmd = [
            "livekit-agents", "run-job",
            "--agent", "outbound-caller",
            "--metadata", json.dumps(dial_info)
        ]
        '''
        cmd= [
            "lk", 
            "dispatch", 
            "create",
            "--new-room",
            "--agent-name",
            "outbound-caller",
            "--metadata",
            json.dumps(dial_info)

        ]
        subprocess.Popen(cmd)
    
    asyncio.create_task(launch_job())
    return {"status": "scheduled"}
