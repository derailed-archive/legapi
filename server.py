import multiprocessing

import uvicorn

if __name__ == '__main__':
    uvicorn.run(
        'derailed.app:app', host='0.0.0.0', reload=False, port=8080, workers=multiprocessing.cpu_count()
    )
