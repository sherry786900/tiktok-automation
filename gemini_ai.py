import os
import google.generativeai as genai


def generate_title_hashtags(label=''):
    try:
        genai.configure(api_key=os.environ.get('GEMINI_API_KEY', ''))
        model = genai.GenerativeModel('gemini-1.5-flash')

        part_info = ''
        if 'part 1' in label.lower():
            part_info = 'Yeh Part 1 hai — ending suspenseful honi chahiye.'
        elif 'part 2' in label.lower():
            part_info = 'Yeh Part 2 hai — story complete hoti hai.'

        prompt = (
            f"Tu ek Urdu TikTok story creator hai. {part_info}\n"
            f"Ek viral TikTok ke liye do:\n"
            f"1. TITLE: Catchy Roman Urdu title (max 150 chars) — curiosity aur suspense ho\n"
            f"2. HASHTAGS: 12 hashtags — trending + Urdu + story mix\n\n"
            f"Sirf is format mein jawab do:\n"
            f"TITLE: ...\n"
            f"HASHTAGS: #tag1 #tag2 ..."
        )

        r = model.generate_content(prompt)
        title, hashtags = '', ''
        for line in r.text.strip().split('\n'):
            if line.startswith('TITLE:'):
                title = line.replace('TITLE:', '').strip()
            elif line.startswith('HASHTAGS:'):
                hashtags = line.replace('HASHTAGS:', '').strip()

        return (
            title or f'Aik Anokhi Kahani {label}',
            hashtags or '#urdustory #viral #tiktok #kahani #trending'
        )
    except Exception as e:
        print(f'Gemini error: {e}')
        return f'Viral Kahani {label}', '#urdustory #viral #tiktok #trending #kahani'
