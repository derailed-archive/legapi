from discoursy.app import app
import multiprocessing

if __name__ == '__main__':
    app.run(workers=multiprocessing.cpu_count(), noisy_exceptions=True)
