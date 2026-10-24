import os
import uuid
import threading
import startup
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from processor import VideoProcessor
from gemini_ai import generate_title_hashtags
from tiktok_upload import TikTokUploader
from drive_helper import DriveHelper

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

os.makedirs('uploads', exist_ok=True)
os.makedirs('outputs', exist_ok=True)

jobs = {}


def run_job(job_id, video_path, video_type, drive_folder_id, montage_start):
    try:
        def update(status, msg):
            jobs[job_id]['status'] = status
            jobs[job_id]['message'] = msg
            print(f'[{job_id}] {msg}')

        update('downloading', '📥 Drive se clips aur sound download ho rahe hain...')
        drive = DriveHelper()
        clips, sound_path = drive.download_all(drive_folder_id, job_id)
        print(f'Clips: {len(clips)}, Sound: {sound_path}')

        update('processing', '🎬 Video process ho rahi hai...')
        processor = VideoProcessor()

        if video_type == 'main':
            output = processor.process_main(video_path, clips, sound_path, job_id, montage_start)
            outputs = [{'path': output, 'label': 'Main Video'}]

        else:  # part
            update('processing', '🤖 Gemini suspense point dhundh raha hai...')
            p1, p2 = processor.process_parts(video_path, clips, sound_path, job_id, montage_start)
            outputs = [
                {'path': p1, 'label': 'Part 1'},
                {'path': p2, 'label': 'Part 2'},
            ]

        update('uploading', '✍️ Gemini title aur hashtags bana raha hai...')
        uploader = TikTokUploader()
        results = []

        for item in outputs:
            title, hashtags = generate_title_hashtags(item['label'])
            update('uploading', f'📱 {item["label"]} TikTok pe upload ho rahi hai...')
            url = uploader.upload(item['path'], title, hashtags)
            results.append({
                'label': item['label'],
                'title': title,
                'hashtags': hashtags,
                'tiktok_url': url,
            })

        jobs[job_id]['status'] = 'done'
        jobs[job_id]['message'] = '✅ Sab ho gaya!'
        jobs[job_id]['results'] = results

    except Exception as e:
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['message'] = f'❌ Error: {str(e)}'
        print(f'[{job_id}] ERROR: {e}')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'video' not in request.files:
        return jsonify({'error': 'Video file nahi mili'}), 400

    file = request.files['video']
    video_type = request.form.get('type', 'main')
    drive_id = request.form.get('drive_id', '').strip()
    montage_start = int(request.form.get('montage_start', 90))

    if not drive_id:
        return jsonify({'error': 'Google Drive folder ID daalo'}), 400

    job_id = str(uuid.uuid4())[:8]
    save_path = os.path.join('uploads', f'{job_id}_{secure_filename(file.filename)}')
    file.save(save_path)

    jobs[job_id] = {'status': 'queued', 'message': 'Shuru hone wala hai...', 'results': []}

    t = threading.Thread(target=run_job, args=(job_id, save_path, video_type, drive_id, montage_start))
    t.daemon = True
    t.start()

    return jsonify({'job_id': job_id})


@app.route('/status/<job_id>')
def status(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job nahi mili'}), 404
    return jsonify(jobs[job_id])


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
