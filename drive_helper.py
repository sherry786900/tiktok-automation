import os
import requests

GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', '')


def list_drive_files(folder_id):
    """Drive folder ki saari files lo"""
    url = (
        f'https://www.googleapis.com/drive/v3/files'
        f'?q="{folder_id}"+in+parents'
        f'&fields=files(id,name,mimeType)'
        f'&key={GOOGLE_API_KEY}'
    )
    r = requests.get(url)
    if r.status_code != 200:
        raise RuntimeError(f'Drive API error: {r.text}')
    return r.json().get('files', [])


def download_file(file_id, local_path):
    """Single file download karo"""
    if os.path.exists(local_path):
        return local_path
    url = f'https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&key={GOOGLE_API_KEY}'
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'wb') as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return local_path
    raise RuntimeError(f'Download failed: {local_path}')


class DriveHelper:

    def download_all(self, folder_id, job_id):
        """
        Drive folder se sab download karo:
        - clip1.mp4, clip2.mp4 ... (montage clips)
        - sound.mp3 / sound.mp4 (background sound)
        Returns: (clips_list, sound_path)
        """
        base_dir = f'uploads/drive_{job_id}'
        os.makedirs(base_dir, exist_ok=True)

        files = list_drive_files(folder_id)
        if not files:
            raise RuntimeError('Drive folder khali hai!')

        clips = []
        sound_path = None

        # Files sort karo naam se
        files.sort(key=lambda x: x['name'].lower())

        for f in files:
            name = f['name'].lower()
            fid = f['id']
            local = os.path.join(base_dir, f['name'])

            # Sound file check karo
            if name.startswith('sound'):
                sound_path = download_file(fid, local)
                print(f'Sound downloaded: {f["name"]}')

            # Clip files check karo (clip1, clip2 etc)
            elif name.startswith('clip'):
                clip_path = download_file(fid, local)
                clips.append(clip_path)
                print(f'Clip downloaded: {f["name"]}')

        if not clips:
            raise RuntimeError('Koi clip nahi mili! clip1.mp4, clip2.mp4 naam rakho Drive pe.')

        if not sound_path:
            raise RuntimeError('Sound file nahi mili! sound.mp3 naam rakho Drive pe.')

        # Clips ko number ke hisaab se sort karo (clip1, clip2, clip3...)
        clips.sort(key=lambda x: ''.join(filter(str.isdigit, os.path.basename(x))) or '0')

        return clips, sound_path
