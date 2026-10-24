import os
import subprocess
import json
import random
import math

SIZE = 1080
FPS = 30
SPEED = 1.20
PIECE_LEN = 0.45      # Har clip ka piece 0.45 sec
DIP_DUR = 0.35        # Dip-to-dark transition
FADE = 0.18           # Main video fade in/out


def run_cmd(cmd, label=''):
    print(f'Running: {label or cmd[:80]}')
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f'FFmpeg error [{label}]:\n{result.stderr[-1000:]}')
    return result.stdout


def get_duration(path):
    cmd = f'ffprobe -v quiet -print_format json -show_format "{path}"'
    out = subprocess.check_output(cmd, shell=True).decode()
    return float(json.loads(out)['format']['duration'])


def make_square_clip(inp, out, speed=1.0, ss=None, to=None, has_audio=True):
    """
    Clip ko 1:1 square karo, speed lagao.
    ss/to se trim karo (seconds).
    """
    trim = ''
    if ss is not None:
        trim += f' -ss {ss:.3f}'
    if to is not None:
        trim += f' -to {to:.3f}'

    vf = (
        f"setpts={1/speed:.6f}*PTS,"
        f"scale={SIZE}:{SIZE}:force_original_aspect_ratio=increase,"
        f"crop={SIZE}:{SIZE},"
        f"fps={FPS}"
    )

    if has_audio:
        af = f"-af atempo={speed:.2f}"
        audio_out = '-c:a aac -b:a 128k'
    else:
        af = '-an'
        audio_out = '-an'

    cmd = (
        f'ffmpeg -y{trim} -i "{inp}" '
        f'-vf "{vf}" {af} '
        f'-c:v libx264 -preset fast -crf 23 '
        f'{audio_out} "{out}"'
    )
    run_cmd(cmd, f'square clip → {os.path.basename(out)}')


def extract_audio_duration(sound_path):
    """Sound file ki duration lo"""
    return get_duration(sound_path)


def build_montage(clips, sound_path, tmp_dir, job_id):
    """
    Nayi montage system:
    1. Har clip ke 0.45s pieces banao
    2. Shuffle karo
    3. Sound ki length tak pieces lagao
    4. Sound upar se chalao
    5. Dip-to-dark transitions
    """
    os.makedirs(tmp_dir, exist_ok=True)
    sound_dur = extract_audio_duration(sound_path)
    print(f'Sound duration: {sound_dur:.2f}s')

    # Step 1: Har clip ke pieces banao
    all_pieces = []
    for ci, clip in enumerate(clips):
        clip_dur = get_duration(clip)
        num_pieces = max(1, int(clip_dur / PIECE_LEN))
        print(f'Clip {ci+1}: {clip_dur:.1f}s → {num_pieces} pieces')

        for pi in range(num_pieces):
            start = pi * PIECE_LEN
            end = min(start + PIECE_LEN, clip_dur)
            if end - start < 0.2:
                continue

            piece_out = f'{tmp_dir}/piece_{ci}_{pi}.mp4'
            make_square_clip(clip, piece_out, speed=1.0, ss=start, to=end, has_audio=False)
            all_pieces.append(piece_out)

    if not all_pieces:
        raise RuntimeError('Koi pieces nahi bane!')

    # Step 2: Shuffle karo
    random.shuffle(all_pieces)

    # Step 3: Sound duration tak pieces select karo
    # Transition time bhi count karo
    selected = []
    total_time = 0.0
    piece_idx = 0

    while total_time < sound_dur:
        if piece_idx >= len(all_pieces):
            # Pieces khatam — dobara shuffle karke repeat karo
            random.shuffle(all_pieces)
            piece_idx = 0

        piece = all_pieces[piece_idx]
        piece_dur = get_duration(piece)
        selected.append(piece)
        total_time += piece_dur
        if total_time < sound_dur:
            total_time += DIP_DUR  # Transition ka time bhi
        piece_idx += 1

    print(f'Total pieces selected: {len(selected)}, estimated duration: {total_time:.1f}s')

    # Step 4: Pieces ko concat karo with dip-to-dark transitions
    if len(selected) == 1:
        video_only = selected[0]
    else:
        video_only = _concat_with_dip(selected, tmp_dir, job_id)

    # Step 5: Sound lagao upar se (video ki original audio replace)
    final_montage = f'{tmp_dir}/montage_final.mp4'
    montage_dur = get_duration(video_only)

    # Sound ko video ki length tak trim/loop karo
    cmd = (
        f'ffmpeg -y -i "{video_only}" -i "{sound_path}" '
        f'-filter_complex "'
        f'[1:a]atrim=0:{montage_dur:.3f},asetpts=PTS-STARTPTS,'
        f'afade=t=out:st={max(0, montage_dur-0.5):.3f}:d=0.5[aout]'
        f'" '
        f'-map 0:v -map "[aout]" '
        f'-c:v copy -c:a aac -b:a 128k '
        f'-t {montage_dur:.3f} '
        f'"{final_montage}"'
    )
    run_cmd(cmd, 'montage + sound merge')

    return final_montage


def _concat_with_dip(pieces, tmp_dir, job_id):
    """Pieces ko dip-to-dark transition ke saath join karo"""
    # Concat list banao (no audio — pure video)
    # Pehle har piece ke end/start pe fade lagao
    faded = []
    for i, piece in enumerate(pieces):
        dur = get_duration(piece)
        out = f'{tmp_dir}/faded_{i}.mp4'

        fade_in = f'fade=t=in:st=0:d={DIP_DUR}:color=black' if i > 0 else ''
        fade_out_st = max(0, dur - DIP_DUR)
        fade_out = f'fade=t=out:st={fade_out_st:.3f}:d={DIP_DUR}:color=black' if i < len(pieces)-1 else ''

        filters = ','.join(f for f in [fade_in, fade_out] if f)
        vf = f'-vf "{filters}"' if filters else ''

        cmd = f'ffmpeg -y -i "{piece}" {vf} -c:v libx264 -preset fast -crf 23 -an "{out}"'
        run_cmd(cmd, f'fade piece {i}')
        faded.append(out)

    # Concat list file
    list_file = f'{tmp_dir}/concat_{job_id}.txt'
    with open(list_file, 'w') as f:
        for fp in faded:
            f.write(f"file '{os.path.abspath(fp)}'\n")

    out_concat = f'{tmp_dir}/video_only.mp4'
    cmd = (
        f'ffmpeg -y -f concat -safe 0 -i "{list_file}" '
        f'-c:v libx264 -preset fast -crf 23 -an "{out_concat}"'
    )
    run_cmd(cmd, 'concat all pieces')
    return out_concat


class VideoProcessor:

    def process_main(self, video_path, clips, sound_path, job_id, montage_start=90):
        """
        main.mp4 process karo:
        - Speed 1.2x, 1:1 square
        - montage_start seconds ke baad montage insert karo
        - Montage = shuffled 0.45s pieces + sound
        """
        tmp = f'outputs/tmp_{job_id}'
        os.makedirs(tmp, exist_ok=True)
        out_dir = 'outputs'

        total_dur = get_duration(video_path)
        # montage_start speed se adjust karo (1.2x pe video fast chalta hai)
        real_start = montage_start / SPEED

        if real_start >= total_dur:
            real_start = total_dur * 0.5

        # Part A: 0 → real_start
        part_a = f'{tmp}/part_a.mp4'
        make_square_clip(video_path, part_a, speed=SPEED, ss=0, to=real_start)

        # Part B: real_start → end
        part_b = f'{tmp}/part_b.mp4'
        make_square_clip(video_path, part_b, speed=SPEED, ss=real_start)

        # Montage banao
        montage = build_montage(clips, sound_path, f'{tmp}/montage', job_id)

        # Sab join karo: A + Montage + B
        final = f'{out_dir}/{job_id}_main.mp4'
        self._join_three(part_a, montage, part_b, final, tmp, job_id)

        return final

    def process_parts(self, video_path, clips, sound_path, job_id, montage_start=90):
        """
        part_video.mp4:
        - Gemini se cut point dhundho
        - Part 1 aur Part 2 banao
        - Dono mein montage add karo (1:30 ke baad)
        """
        tmp = f'outputs/tmp_{job_id}'
        os.makedirs(tmp, exist_ok=True)
        out_dir = 'outputs'

        total_dur = get_duration(video_path)
        cut_ratio = self._gemini_cut(video_path, total_dur)
        cut_time = total_dur * cut_ratio
        print(f'Cut point: {cut_time:.1f}s (ratio: {cut_ratio:.2f})')

        # Raw parts
        raw1 = f'{tmp}/raw_part1.mp4'
        raw2 = f'{tmp}/raw_part2.mp4'
        make_square_clip(video_path, raw1, speed=SPEED, ss=0, to=cut_time)
        make_square_clip(video_path, raw2, speed=SPEED, ss=cut_time)

        # Montage (ek hi — dono parts mein same sound/clips)
        montage = build_montage(clips, sound_path, f'{tmp}/montage', job_id)

        real_start = montage_start / SPEED

        # Part 1 mein montage
        dur1 = get_duration(raw1)
        part1_final = f'{out_dir}/{job_id}_part1.mp4'
        if real_start < dur1:
            p1a = f'{tmp}/p1a.mp4'
            p1b = f'{tmp}/p1b.mp4'
            make_square_clip(raw1, p1a, speed=1.0, ss=0, to=real_start)
            make_square_clip(raw1, p1b, speed=1.0, ss=real_start)
            self._join_three(p1a, montage, p1b, part1_final, tmp, f'{job_id}_p1')
        else:
            run_cmd(f'ffmpeg -y -i "{raw1}" -c copy "{part1_final}"', 'part1 copy')

        # Part 2 mein montage
        dur2 = get_duration(raw2)
        part2_final = f'{out_dir}/{job_id}_part2.mp4'
        if real_start < dur2:
            p2a = f'{tmp}/p2a.mp4'
            p2b = f'{tmp}/p2b.mp4'
            make_square_clip(raw2, p2a, speed=1.0, ss=0, to=real_start)
            make_square_clip(raw2, p2b, speed=1.0, ss=real_start)
            self._join_three(p2a, montage, p2b, part2_final, tmp, f'{job_id}_p2')
        else:
            run_cmd(f'ffmpeg -y -i "{raw2}" -c copy "{part2_final}"', 'part2 copy')

        return part1_final, part2_final

    def _join_three(self, a, mid, b, output, tmp, jid):
        """3 clips join karo"""
        list_file = f'{tmp}/join_{jid}.txt'
        with open(list_file, 'w') as f:
            for p in [a, mid, b]:
                f.write(f"file '{os.path.abspath(p)}'\n")
        cmd = (
            f'ffmpeg -y -f concat -safe 0 -i "{list_file}" '
            f'-c:v libx264 -preset fast -crf 23 -c:a aac -b:a 128k "{output}"'
        )
        run_cmd(cmd, f'join → {os.path.basename(output)}')

    def _gemini_cut(self, video_path, total_dur):
        """Gemini se suspense cut point lo"""
        try:
            import google.generativeai as genai
            import os
            genai.configure(api_key=os.environ.get('GEMINI_API_KEY', ''))
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = (
                f"Story video hai, total {total_dur:.0f} seconds. "
                f"Part 1 suspense/cliffhanger pe khatam ho. "
                f"Cut point 40%% se 60%% ke beech do. "
                f"Sirf ek number do jaise 0.45 — koi aur text nahi."
            )
            r = model.generate_content(prompt)
            ratio = float(r.text.strip())
            return max(0.40, min(0.60, ratio))
        except:
            return 0.50
