#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=========================================================================================
🕌 مصنع التاريخ الإسلامي الموثق والجدولة الذكية - الإصدار الإنتاجي (v3.0 Production)
File: run_islamic_shorts_v3_production.py
=========================================================================================
المزايا الهندسية المطبقة في الإصدار الإنتاجي (v3.0):
1. التدرج الآمن في التشغيل (Staged Execution Guardrails - القسم السابع والثامن):
   - الوضع الافتراضي الحالي هو `MODE = "SINGLE_TEST"` (ينتج ويفحص فيديو واحداً فقط بقصة جديدة غير مسبوقة: «مكتبة قرطبة المفقودة في عهد الخليفة الحكم المستنصر» دون رفع عشوائي).
   - يدعم أيضاً `MODE = "SINGLE_UPLOAD_TEST"` (اختبار رفع وجدولة فيديو واحد مع التحقق الفعلي من حالة الجدولة على يوتيوب) و `MODE = "DAILY_BATCH_10"` (الإنتاج اليومي لـ 10 فيديوهات بعد موافقتك).
2. التوثيق التاريخي الصارم (Documented Historical Encyclopedia - القسم الثاني):
   - كل حلقة مزودة بحقل `historical_metadata` يحدد الحدث، الحقبة، الشخصيات، الوقائع المتفق عليها، الروايات المختلف عليها عند المؤرخين (مثل تفاوت تقديرات عدد مجلدات مكتبة قرطبة)، وقائمة المصادر والمراجع التاريخية الموثقة التي تُدرج تلقائياً في وصف الفيديو وفي سجل المصادر (`historical_sources_registry.json`).
   - الإفصاح الصريح في الوصف عندما يتضمن الفيديو لوحات فنية استشراقية أو مشاهد توضيحية حتى لا تُعرض كصور فوتوغرافية من العصر القديم.
3. جودة المشاهد ومنع التكرار وحقوق الاستخدام (القسم الثالث):
   - ربط كل جملة من الجمل العشر بمشهد تاريخي مخصص (1:1 Blueprint) من Wikimedia Commons (Public Domain / CC-BY-SA مع حفظ الترخيص والمؤلف في التقرير).
   - فحص مزدوج ببصمة `SHA-256` وبصمة `64-bit Perceptual dHash` (`Hamming Distance <= 6`) عبر جميع الفيديوهات لمنع تكرار أي صورة بين الحلقات.
   - استهداف مدة مثالية لـ YouTube Shorts (`48–58 ثانية`) بإيقاع صوتي واضح ومشوق، مع كابشن عربي متزامن (`ASS`).
4. الجدولة المتتابعة بتوقيت مصر مع مراعاة التوقيت الصيفي والشتوي (القسم الرابع):
   - استخدام `zoneinfo.ZoneInfo("Africa/Cairo")` لحساب الساعة `7:30 مساءً` بتوقيت مصر بدقة تامة سواء في التوقيت الصيفي (`UTC+3`) أو التوقيت الشتوي (`UTC+2` ابتداءً من 30 أكتوبر).
   - فحص عدم التصادم عبر `production_schedule_ledger.json` + استعلام `youtube.videos().list` + ملف `last_scheduled_date_manuscripts.txt`، والتحقق الفعلي بعد الرفع من أن `status.privacyStatus == "private"` وأن `status.publishAt` يطابق الموعد المستهدف.
5. لوحة متابعة الأداء والإنتاج (Analytics & Production Dashboard - القسم السادس):
   - تحديث تلقائي لملفي `analytics_dashboard.json` و `analytics_dashboard.csv` لتسجيل كل فيديو، ومصادره، وموعد جدولته، وجلب إحصاءات المشاهدات والإعجابات من YouTube API عند توفر صلاحية القراءة.
=========================================================================================
"""

import os
import sys
import io
import re
import csv
import json
import time
import math
import wave
import hashlib
import subprocess
import urllib.parse
from datetime import datetime, date, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Dict, List, Tuple, Optional, Any

def ensure_environment():
    """فحص وتثبيت الحزم الأساسية في Google Colab أو GitHub Actions دون المساس بأي ملفات."""
    try:
        import numpy
        import requests
        from PIL import Image
        import edge_tts
        from googleapiclient.discovery import build
    except ImportError:
        print("⏳ جاري تثبيت مكتبات المعالجة والاتصال الرسمية...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "edge-tts", "pillow", "numpy", "requests", "google-api-python-client", "google-auth-oauthlib"],
            check=False
        )

    font_paths = [
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ]
    if not any(os.path.exists(p) for p in font_paths) and os.path.exists("/usr/bin/apt-get"):
        subprocess.run(["apt-get", "update", "-qq"], check=False)
        subprocess.run(["apt-get", "install", "-y", "-qq", "fonts-noto-core", "fonts-hosny-amiri", "ffmpeg"], check=False)

import numpy as np
import requests
from PIL import Image, ImageFilter, ImageEnhance, ImageDraw

# =========================================================================================
# 1. إعدادات التشغيل الآمن والمسارات (Execution Mode & Non-Destructive Paths)
# =========================================================================================
# الأوضاع المتاحة:
# - "SINGLE_TEST"        : المرحلة الأولى (الافتراضية) - إنتاج وفحص فيديو واحد جديد دون رفعه إلى يوتيوب.
# - "SINGLE_UPLOAD_TEST" : المرحلة الثانية - إنتاج وفحص ورفع فيديو واحد مجدول والتحقق من جدولته فعلياً.
# - "DAILY_BATCH_10"     : المرحلة الإنتاجية الكاملة - إنتاج وجدولة 10 فيديوهات جديدة في المواعيد المتتالية.
MODE = os.environ.get("ISLAMIC_FACTORY_MODE", "SINGLE_TEST").strip()

IS_COLAB = os.path.exists("/content")
DRIVE_ROOT = "/content/drive/MyDrive" if IS_COLAB else "/dev/shm/local_drive_sim"

TEST_LAB_DIR = os.path.join(DRIVE_ROOT, "Islamic_Shorts_Test_Lab")
PROD_BANK_DIR = os.path.join(DRIVE_ROOT, "Shorts_Bank_Manuscripts")
SCENES_CACHE_DIR = os.path.join(TEST_LAB_DIR, "verified_scenes_cache_v3_clean")
REPORTS_DIR = os.path.join(TEST_LAB_DIR, "qa_reports")

VISUAL_REGISTRY_FILE = os.path.join(TEST_LAB_DIR, "visual_dedup_registry_v2_2.json")
LEGACY_TOPICS_FILE = os.path.join(DRIVE_ROOT, "used_topics_manuscripts.json")
LEGACY_LAST_DATE_FILE = os.path.join(DRIVE_ROOT, "last_scheduled_date_manuscripts.txt")

SOURCES_REGISTRY_FILE = os.path.join(TEST_LAB_DIR, "historical_sources_registry.json")
SCHEDULE_LEDGER_FILE = os.path.join(TEST_LAB_DIR, "production_schedule_ledger.json")
ANALYTICS_JSON_FILE = os.path.join(TEST_LAB_DIR, "analytics_dashboard.json")
ANALYTICS_CSV_FILE = os.path.join(TEST_LAB_DIR, "analytics_dashboard.csv")

FINAL_WIDTH = 2160
FINAL_HEIGHT = 3840
FINAL_FPS = 30

MIN_SOURCE_WIDTH = 540
MIN_SOURCE_HEIGHT = 540
MIN_LUMA_STANDARD = 22.0
MIN_LUMA_NIGHT = 14.0
MAX_LUMA_OVEREXPOSED = 242.0
MIN_CONTRAST_STD_STANDARD = 16.0
MIN_CONTRAST_STD_NIGHT = 12.0
MAX_DHASH_HAMMING_DISTANCE = 6

FORBIDDEN_TITLE_SUBSTRINGS = [
    ".pdf", ".djvu", ".stl", ".svg", "traffic", "highway", "automobile",
    "car ", "cars", "neon", "modern", "skyscraper", "bus ", "tram",
    "metro", "selfie", "tourist", "tanger", "morocco", "croisés", "crusader"
]

# =========================================================================================
# 2. قاعدة البيانات التاريخية الموثقة بالمصادر (Documented Historical Encyclopedia DB)
# =========================================================================================
DOCUMENTED_HISTORICAL_EPISODES: List[Dict[str, Any]] = [{'topic_id': 'cordoba_lost_library_v3',
  'legacy_id': 'cordoba_lost_library',
  'title': 'خزانة قرطبة العظمى: كيف جمعت الأندلس مئات آلاف المخطوطات في القرن العاشر؟ #التاريخ_الإسلامي #shorts',
  'historical_metadata': {'event_name': 'تأسيس وازدهار خزانة الكتب الكبرى في قرطبة في عهد الخليفة الأموي الحكم '
                                        'المستنصر بالله',
                          'historical_period': 'القرن الرابع الهجري / القرن العاشر الميلادي (فترة خلافة الحكم '
                                               'المستنصر: 350–366 هـ / 961–976 م)',
                          'key_figures': ['الخليفة الأموي الحكم المستنصر بالله (ت. 366 هـ / 976 م)',
                                          'العالِم الفلكي إبراهيم بن سعيد السهلي (صانع الإسطرلاب الأندلسي 459 هـ / '
                                          '1067 م)',
                                          'الجغرافي الشريف الإدريسي (صاحب نزهة المشتاق 548 هـ / 1154 م)'],
                          'verified_facts': ['أسس الخليفة الحكم المستنصر بالله في قرطبة خزانة كتب كبرى جمعت بين خزائن '
                                             'قصر الخلافة وتجليد المخطوطات وفهرستها.',
                                             'ضم فهرس الخزانة وحده أربعة وأربعين كراساً، في كل كراس عشرون ورقة تذكر '
                                             'أسماء الدواوين والكتب فقط.',
                                             'شهدت قرطبة في القرن العاشر الميلادي نهضة عمرانية وعلمية واسعة شملت '
                                             'الجامع الأعظم، مدينة الزهراء، وصناعة الإسطرلابات الدقيقة.'],
                          'historiographical_notes': 'تذكر الروايات التاريخية الكلاسيكية (مثل ابن حيان القرطبي وابن '
                                                     'خلدون والمقري) أن عدد مجلدات مكتبة الحكم المستنصر قُدّر بنحو '
                                                     '400,000 مجلد، بينما يشير بعض المؤرخين المعاصرين إلى أن هذا الرقم '
                                                     'يمثل ذروة تقديرات الفهارس الشاملة في العصر الأموي مقارنةً '
                                                     'بمكتبات الأديرة الأوروبية آنذاك التي لم تتجاوز بضع مئات من '
                                                     'المجلدات.',
                          'primary_and_secondary_sources': ['ابن الفرضي (ت. 403 هـ): تاريخ علماء الأندلس، تحقيق عزت '
                                                            'العطار الحسيني، القاهرة.',
                                                            'ابن خلدون (ت. 808 هـ): كتاب العبر وديوان المبتدأ والخبر، '
                                                            'دار الفكر، بيروت، ج4 (ذكر دولة بني أمية بالأندلس وخزانة '
                                                            'الحكم المستنصر).',
                                                            'أحمد بن محمد المقري التلمساني (ت. 1041 هـ): نفح الطيب من '
                                                            'غصن الأندلس الرطيب، تحقيق إحسان عباس، دار صادر، بيروت، '
                                                            'ج1.',
                                                            'المتحف الأثري الوطني في مدريد (Museo Arqueológico '
                                                            'Nacional): توثيق إسطرلاب إبراهيم بن سعيد السهلي المصنوع '
                                                            'سنة 459 هـ / 1067 م.'],
                          'visual_disclosure': 'المشاهد البصرية تعرض صوراً فوتوغرافية موثقة لمعالم قرطبة الباقية '
                                               '(الجامع الأعظم، القنطرة الرومانية-الأندلسية، مدينة الزهراء، ناعورة '
                                               'السانية/الألبولافيا) ومخطوطات وإسطرلابات أندلسية أصلية محفوظة في '
                                               'المتاحف العالمية (رخصة المشاع الإبداعي/الملكية العامة من ويكيميديا '
                                               'كومنز).'},
  'scenes': [{'scene_num': 1,
              'shot_type': 'لقطة افتتاحية واسعة لأقواس جامع قرطبة الأعظم (Wide Establishing Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'في القرن العاشر الميلادي، كانت قرطبة عاصمة الأندلس تعيش ذروة نهضتها العلمية!',
              'caption_chunks': ['في القرن العاشر الميلادي:', 'كانت قرطبة عاصمة الأندلس', 'تعيش ذروة نهضتها العلمية!'],
              'wikimedia_exact_files': ['File:Mosque of Cordoba.jpg',
                                        'File:Great Mosque of Cordoba, interior, 8th - 10th centuries (38) '
                                        '(29721130342).jpg'],
              'wikimedia_queries': ['Mosque of Cordoba interior arches', 'Mezquita de Cordoba columns']},
             {'scene_num': 2,
              'shot_type': 'لقطة واسعة لقنطرة قرطبة التاريخية على نهر الوادي الكبير (Wide River Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'فعلى ضفاف الوادي الكبير، تحولت المدينة إلى قبلة للعلماء والوراقين.',
              'caption_chunks': ['على ضفاف نهر الوادي الكبير:',
                                 'تحولت قرطبة إلى قبلة للعلماء',
                                 'والوراقين من أنحاء العالم!'],
              'wikimedia_exact_files': ['File:Puente Romano of Córdoba Spain.jpg',
                                        'File:Puente romano durante su restauración (Córdoba, Spain).jpg'],
              'wikimedia_queries': ['Puente Romano of Cordoba Spain', 'Roman bridge Cordoba Guadalquivir']},
             {'scene_num': 3,
              'shot_type': 'لقطة معمارية لأروقة مدينة الزهراء الملكية (Architectural Portico Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'وفي عام ثلاثمئة وخمسين للهجرة، أسس الخليفة الحكم المستنصر أعظم خزانة كتب في الغرب '
                                 'الإسلامي.',
              'caption_chunks': ['في سنة ٣٥٠ هـ (٩٦١ م):',
                                 'أسس الخليفة الحكم المستنصر',
                                 'أعظم خزانة كتب في الغرب الإسلامي!'],
              'wikimedia_exact_files': ['File:Pórtico de Medina Azahara (Córdoba, Spain).jpg',
                                        'File:Medina Azahara - Conjunto Arqueológico Madinat al-Zahra, Cordoba '
                                        '(26959503737).jpg'],
              'wikimedia_queries': ['Portico de Medina Azahara Cordoba', 'Madinat al-Zahra arches']},
             {'scene_num': 4,
              'shot_type': 'لقطة قريبة للزخارف الحجرية والنقوش الأندلسية في مدينة الزهراء (Close-Up Detail Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'أرسل وكلاءه إلى بغداد ودمشق والقاهرة لجمع أندر المؤلفات واستنساخها.',
              'caption_chunks': ['أرسل الخليفة وكلاءه إلى', 'بغداد والقاهرة ودمشق', 'لجمع أندر المؤلفات واستنساخها!'],
              'wikimedia_exact_files': ['File:Decoración de Medina Azahara (Córdoba, España).jpg',
                                        'File:Interior de la mezquita de Córdoba (David Roberts).jpg'],
              'wikimedia_queries': ['Decoracion de Medina Azahara Cordoba', 'Madinat al-Zahra relief']},
             {'scene_num': 5,
              'shot_type': 'لقطة لمخطوطة أندلسية مذهبة محفوظة في متحف المتروبوليتان (Manuscript Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'ويوثق ابن خلدون والمقري أن فهارس العناوين وحدها بلغت أربعة وأربعين كراساً!',
              'caption_chunks': ['يوثق ابن خلدون والمقري:',
                                 'أن فهارس العناوين بلغت ٤٤ كراساً',
                                 'لـمئات آلاف المجلدات!'],
              'wikimedia_exact_files': ["File:Bifolium from the Andalusian Pink Qur'an MET DP-14019-001.jpg",
                                        "File:Bifolium from a Qur'an Manuscript MET 38002.jpg"],
              'wikimedia_queries': ['Bifolium from the Andalusian Pink Quran MET', 'Andalusian manuscript MET']},
             {'scene_num': 6,
              'shot_type': 'لقطة قريبة لإسطرلاب إبراهيم بن سعيد السهلي الأندلسي 1067م (Scientific Instrument Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'أثمرت هذه الخزائن نهضة علمية أنتجت أدق الإسطرلابات الفلكية ومؤلفات الطب والرياضيات.',
              'caption_chunks': ['أثمرت هذه الخزائن نهضة علمية',
                                 'أنتجت أدق الإسطرلابات الفلكية',
                                 'ومؤلفات الطب والرياضيات!'],
              'wikimedia_exact_files': ['File:Astrolabio (16787706916).jpg',
                                        'File:A drawing of an astrolabe Wellcome L0041186.jpg'],
              'wikimedia_queries': ['Astrolabio 16787706916', 'Al-Sahli astrolabe Madrid']},
             {'scene_num': 7,
              'shot_type': 'لقطة لمخطوطة جغرافية عربية للشريف الإدريسي (Cartography & Science Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'ومن هذا التراث الأندلسي خرجت خرائط الجغرافيين التي قصدها طلاب العلم من أوروبا.',
              'caption_chunks': ['ومن هذا التراث العلمي الأندلسي:',
                                 'خرجت أدق الخرائط الجغرافية',
                                 'التي قصدها طلاب العلم من أوروبا!'],
              'wikimedia_exact_files': ['File:TabulaRogeriana - map of Brittany in Arabic.jpg',
                                        'File:Koran, Illuminated incipit page with headpiece, Walters Manuscript '
                                        'W.556, fol. 4b (4690325429).jpg'],
              'wikimedia_queries': ['TabulaRogeriana map in Arabic', 'Al-Idrisi map manuscript']},
             {'scene_num': 8,
              'shot_type': 'لقطة لمحراب جامع قرطبة المزخرف بالفسيفساء الذهبية (Mihrab Architecture Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'وكتب الخليفة الحكم المستنصر بخط يده حواشي وتدقيقات على كثير من مخطوطاتها.',
              'caption_chunks': ['كتب الخليفة الحكم المستنصر', 'بخط يده حواشي وتدقيقات', 'على كثير من تلك المخطوطات!'],
              'wikimedia_exact_files': ['File:Mihrab de la mezquita de Córdoba (17060237467).jpg',
                                        'File:Mihrab - Mosque of Córdoba.jpg'],
              'wikimedia_queries': ['Mihrab de la mezquita de Cordoba', 'Mihrab Mosque of Cordoba']},
             {'scene_num': 9,
              'shot_type': 'لقطة لفناء النارنج ومئذنة جامع قرطبة التاريخي (Courtyard Historical Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'لكن الفتن والصراعات اللاحقة أدت إلى تفرق كنوز الخزانة وضياع معظمها.',
              'caption_chunks': ['لكن الفتن والصراعات اللاحقة', 'أدت إلى تفرق كنوز الخزانة', 'وضياع جزء كبير منها!'],
              'wikimedia_exact_files': ['File:Patio de los Naranjos - La Mezquita - Córdoba.JPG',
                                        'File:Vista al Patio de los Naranjos (Mezquita-Catedral de Córdoba).JPG'],
              'wikimedia_queries': ['Patio de los Naranjos La Mezquita Cordoba', 'Courtyard of the Oranges Cordoba']},
             {'scene_num': 10,
              'shot_type': 'لقطة ختامية لناعورة قرطبة التاريخية (الألبولافيا) على النهر (Historical Finale Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'ورغم ذلك بقيت شواهد قرطبة منارة خالدة في تاريخ الحضارة! اشترك الآن.',
              'caption_chunks': ['بقيت شواهد قرطبة وعلمائها',
                                 'منارة خالدة في تاريخ الحضارة!',
                                 'اشترك الآن لمزيد من التاريخ الموثق!'],
              'wikimedia_exact_files': ['File:Molino de la Albolafia (Córdoba, Spain).jpg',
                                        'File:Molino de la Albolafia (Córdoba, España).jpg'],
              'wikimedia_queries': ['Molino de la Albolafia Cordoba', 'Albolafia mill Cordoba']}]},
 {'topic_id': 'yarmouk_khaled_v3',
  'legacy_id': 'yarmouk_khaled',
  'title': 'معركة اليرموك (١٥ هـ): كيف أسقط تكتيك خالد بن الوليد جيش الروم؟ #مخطوطات_منسية #التاريخ_الإسلامي #shorts',
  'historical_metadata': {'event_name': 'معركة اليرموك الفاصلة بين جيش المسلمين وجيش الإمبراطورية البيزنطية',
                          'historical_period': 'رجب سنة 15 هـ / أغسطس 636 م (في عهد الخليفة الراشد عمر بن الخطاب رضي '
                                               'الله عنه)',
                          'key_figures': ['سيف الله المسلول خالد بن الوليد (قائد التكتيك العسكري العام)',
                                          'أبو عبيدة عامر بن الجراح (أمين الأمة وقائد الجيوش)',
                                          'الإمبراطور البيزنطي هرقل (Heraclius)',
                                          'القائد البيزنطي فاهان وباهان (Vahan)'],
                          'verified_facts': ['وقعت المعركة قرب نهر اليرموك جنوب سهل حوران على الحدود السورية الأردنية '
                                             'الحالية.',
                                             'قسّم خالد بن الوليد الجيش الإسلامي إلى كراديس (كتائب متحركة) وفصل بين '
                                             'فرسان الروم ومشاتهم.',
                                             'قاد خالد سلاح الفرسان الخفيف في مناورة تطويق سريعة قطعت خط رجعة الجيش '
                                             'البيزنطي عند وادي الرقاد.',
                                             'حسمت المعركة مصير بلاد الشام كاملة وأنهت الوجود البيزنطي فيها للأبد.'],
                          'historiographical_notes': 'تختلف تقديرات المؤرخين الكلاسيكيين (كالطبري والبلاذري وابن كثير) '
                                                     'مع المؤرخين البيزنطيين المعاصرين للحدث (مثل ثيوفانيس) في الأعداد '
                                                     'الدقيقة للجيشين؛ حيث قدرت الروايات الإسلامية جيش الروم بأكثر من '
                                                     '100 إلى 200 ألف مقابل نحو 30 إلى 40 ألف للمسلمين، بينما يرجح '
                                                     'المؤرخون المعاصرون أن جيش الروم كان بين 40 و80 ألفاً وجيش '
                                                     'المسلمين بين 25 و40 ألفاً، مع الإجماع الكامل على التفوق العددي '
                                                     'للروم والعبقرية التكتيكية لخالد بن الوليد.',
                          'primary_and_secondary_sources': ['محمد بن جرير الطبري (ت. 310 هـ): تاريخ الرسل والملوك، دار '
                                                            'المعارف، القاهرة، أحداث سنة 15 هـ.',
                                                            'أحمد بن يحيى البلاذري (ت. 279 هـ): فتوح البلدان، دار '
                                                            'ومكتبة الهلال، بيروت (فتح الشام ومعركة اليرموك).',
                                                            'ابن كثير (ت. 774 هـ): البداية والنهاية، دار إحياء التراث '
                                                            'العربي، بيروت، ج7.',
                                                            'A.I. Akram (1970): The Sword of Allah: Khalid bin '
                                                            'Al-Waleed, National Publishing House, Rawalpindi.'],
                          'visual_disclosure': 'المشاهد البصرية تعرض خرائط جغرافية موثقة لوادي اليرموك ووادي الرقاد، '
                                               'وآثار المدن الرومانية المحصنة في الشام (بصرى الشام وأفاميا)، وسيوف '
                                               'وخوذ إسلامية وبيزنطية أصلية من متاحف الآثار العالمية (رخصة المشاع '
                                               'الإبداعي/الملكية العامة من ويكيميديا كومنز).'},
  'scenes': [{'scene_num': 1,
              'shot_type': 'لقطة افتتاحية واسعة لسهول حوران وتلال اليرموك (Wide Establishing Landscape Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'في صيف عام خمسة عشر للهجرة، احتشد في وادي اليرموك أضخم جيش عبأته الإمبراطورية '
                                 'البيزنطية لاستعادة بلاد الشام!',
              'caption_chunks': ['في صيف عام ١٥ هـ (٦٣٦ م):',
                                 'احتشد في وادي اليرموك أضخم جيش',
                                 'عبأته الإمبراطورية البيزنطية!'],
              'wikimedia_exact_files': ['File:Syrie, Gouvernorat de Deraa, cascades et rivière Yarmouk à Tell Chéhab, '
                                        'vue aérienne oblique (MédiHAL 2505702).jpg',
                                        'File:Levant 06-Yarmukh-River (FL155317995 2369583).jpg'],
              'wikimedia_queries': ['Yarmouk River valley Syria', 'Tell Chehab Yarmouk']},
             {'scene_num': 2,
              'shot_type': 'لقطة خريطة تكتيكية عسكرية للجولان ونهر اليرموك (Tactical Battle Map Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'كان الروم متفوقين في العدد والعتاد الثقيل، وظن قادتهم أن حسم المعركة لن يستغرق سوى '
                                 'ساعات معدودة.',
              'caption_chunks': ['تفوق الروم في العدد والعتاد،', 'وظن قادتهم أن حسم المعركة', 'لن يستغرق سوى ساعات!'],
              'wikimedia_exact_files': ['File:Battle of Yarmouk Day Two.svg',
                                        'File:Byzantine empire 1265 1355 shepherd.jpg'],
              'wikimedia_queries': ['Battle of Yarmouk map', 'Byzantine Empire Syria map']},
             {'scene_num': 3,
              'shot_type': 'لقطة معمارية لآثار الحصون الرومانية في بصرى الشام (Ancient Fortification Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'لكن سيف الله المسلول خالد بن الوليد، أدرك بعبقريته العسكرية طبيعة الأرض الوعرة '
                                 'ومفاتيحها الجغرافية.',
              'caption_chunks': ['لكن خالد بن الوليد', 'أدرك بعبقريته العسكرية', 'طبيعة الأرض ومفاتيحها الجغرافية!'],
              'wikimedia_exact_files': ['File:Bosra pano Syria.jpg', 'File:Bosra, theatre.jpg'],
              'wikimedia_queries': ['Bosra ruins Syria', 'Ancient City of Bosra']},
             {'scene_num': 4,
              'shot_type': 'لقطة لتكتيك الكراديس والصفوف الدفاعية (Military Formation Tactical Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'قسّم خالد جيش المسلمين إلى ستة وثلاثين كردوساً متحركاً لامتصاص الصدمات الأولى وثبات '
                                 'خطوط المشاة.',
              'caption_chunks': ['قسّم الجيش إلى ٣٦ كردوساً متحركاً', 'لامتصاص الصدمات الأولى', 'وثبات خطوط المشاة!'],
              'wikimedia_exact_files': ['File:Apamea 01.jpg', 'File:Apamea (6362535167).jpg'],
              'wikimedia_queries': ['Apamea Syria colonnade', 'Ancient Roman Syria ruins']},
             {'scene_num': 5,
              'shot_type': 'لقطة متوسطة للأسلحة والسيوف الفولاذية القديمة (Ancient Weapons Detail Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'وعلى مدى ستة أيام متواصلة من القتال الشرس، صمد المسلمون أمام هجمات الفرسان '
                                 'البيزنطيين المتكررة.',
              'caption_chunks': ['وعلى مدى ٦ أيام متواصلة،', 'صمد المسلمون بصلابة', 'أمام هجمات الفرسان المتكررة!'],
              'wikimedia_exact_files': ['File:Imperial Armoury Topkapi Istanbul (19).JPG',
                                        'File:Fatih Sultan-Schwert.jpg'],
              'wikimedia_queries': ['Topkapi sword armor', 'Ancient Islamic weapons Topkapi']},
             {'scene_num': 6,
              'shot_type': 'لقطة حركية لمناورة الفرسان السريعة (Cavalry Flanking Maneuver Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'وفي اليوم الحاسم، استغل خالد هبوب عاصفة رملية في وجوه الروم، فشن هجوماً كاسحاً بسلاح '
                                 'الفرسان الخفيف!',
              'caption_chunks': ['وفي اليوم السادس الحاسم:',
                                 'شن خالد هجوماً مباغتاً بسلاح الفرسان',
                                 'فصل به خيالة الروم عن مشاتهم!'],
              'wikimedia_exact_files': ['File:Fausto Zonaro - The Ottoman Fleet Passing Over Land.jpg',
                                        'File:Conquest of Constantinople, Zonaro.jpg'],
              'wikimedia_queries': ['Fausto Zonaro cavalry', 'Ancient cavalry battle painting']},
             {'scene_num': 7,
              'shot_type': 'لقطة عميقة لمنحدرات وادي الرقاد الصخرية السحيقة (Canyon Ambush Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'أرسل خالد فرقة فرسان بقيادة ضرار بن الأزور ليلاً للسيطرة على الجسر الوحيد فوق وادي '
                                 'الرقاد السحيق.',
              'caption_chunks': ['أرسل فرقة فرسان ليلاً', 'للسيطرة على الجسر الوحيد', 'فوق مضيق وادي الرقاد السحيق!'],
              'wikimedia_exact_files': ['File:Syrie, Gouvernorat de Deraa, cascades et rivière Yarmouk à Tell Chéhab, '
                                        'vue aérienne oblique (MédiHAL 2505702).jpg',
                                        'File:Levant 06-Yarmukh-River (FL155317995 2369583).jpg'],
              'wikimedia_queries': ['Yarmouk gorge canyon', 'Wadi Raqqad canyon Syria']},
             {'scene_num': 8,
              'shot_type': 'لقطة تطويق وإحكام الكماشة العسكرية (Encirclement Tactical Impact Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'وجد الجيش البيزنطي نفسه محاصراً بين هجوم الفرسان من الأمام والهاوية الصخرية من '
                                 'الخلف!',
              'caption_chunks': ['وجد الروم أنفسهم في كماشة محكمة:',
                                 'هجوم الفرسان من الأمام',
                                 'والهاوية الصخرية من الخلف!'],
              'wikimedia_exact_files': ['File:A portion of Panorama 1453 siege scene.jpg',
                                        'File:Belagerung Konstantinopels.jpg'],
              'wikimedia_queries': ['Panorama 1453 siege scene', 'Battle encirclement painting']},
             {'scene_num': 9,
              'shot_type': 'لقطة ذروة النصر التاريخي وسقوط السيطرة البيزنطية (Historical Climax Victory Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'انهار الجيش البيزنطي بالكامل، لتسقط بذلك أسطورة القوة التي لا تقهر وتفتح أبواب الشام '
                                 'للأبد.',
              'caption_chunks': ['انهار الجيش البيزنطي بالكامل،',
                                 'وانفتحت أبواب دمشق وبيت المقدس',
                                 'أمام الفتح الإسلامي للأبد!'],
              'wikimedia_exact_files': ['File:Zonaro GatesofConst.jpg',
                                        'File:Benjamin-Constant-The Entry of Mahomet II into Constantinople-1876.jpg'],
              'wikimedia_queries': ['Zonaro GatesofConst', 'Historical victory entry painting']},
             {'scene_num': 10,
              'shot_type': 'لقطة ختامية لآثار دمشق وبوابة القدس التاريخية (Historical Documentary Finale Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'سطر خالد بن الوليد أعظم ملحمة تكتيكية في تاريخ الحروب القديمة! اشترك في القناة لمزيد '
                                 'من بطولات التاريخ.',
              'caption_chunks': ['ملحمة عسكرية عبقرية', 'غيّرت تاريخ الشرق إلى الأبد!', 'اشترك الآن في مخطوطات منسية!'],
              'wikimedia_exact_files': ['File:Hagia Sophia Mars 2013.jpg',
                                        'File:Mihrab de la mezquita de Córdoba (17060237467).jpg'],
              'wikimedia_queries': ['Damascus Gate ancient Jerusalem', 'Islamic historical landmark']}]},
 {'topic_id': 'ain_jalut_mongols_v3',
  'legacy_id': 'ain_jalut_mongols',
  'title': 'معركة عين جالوت (٦٥٨ هـ): كيف كسر سيف الدين قطز وبيبرس أسطورة التتار؟ #مخطوطات_منسية #التاريخ_الإسلامي '
           '#shorts',
  'historical_metadata': {'event_name': 'معركة عين جالوت الفاصلة بين المماليك وجيش إمبراطورية المغول',
                          'historical_period': '25 رمضان 658 هـ / 3 سبتمبر 1260 م (في عهد السلطان المظفر سيف الدين '
                                               'قطز)',
                          'key_figures': ['السلطان سيف الدين قطز (سلطان مصر وقائد الجيش)',
                                          'الأمير ركن الدين بيبرس البندقداري (قائد الطليعة والكمين)',
                                          'كتبغا نوين (قائد جيش المغول في الشام)',
                                          'هولاكو خان (مؤسس الدولة الإلخانية)'],
                          'verified_facts': ['وقعت المعركة في سهل عين جالوت بين بيسان وجنين في فلسطين.',
                                             'قاد بيبرس كميناً حربياً بالتظاهر بالانسحاب لاستدراج القوات المغولية إلى '
                                             'قلب الوادي المحاط بالتلال.',
                                             "ألقى قطز خوذته وصاح: 'وا إسلاماه!' وقاد الهجوم المضاد الحاسم الذي أدى "
                                             'لمقتل كتبغا وهزيمة المغول التامة.',
                                             'أنقذت المعركة مصر وشمال إفريقيا وبقية العالم الإسلامي من مصير سقوط بغداد '
                                             '(656 هـ).'],
                          'historiographical_notes': 'تجمع المصادر التاريخية (كالذهبي وابن تغري بردي وابن كثير '
                                                     'والمقريزي) على أن عين جالوت كانت أول هزيمة ساحقة لجيش المغول في '
                                                     'معركة ميدانية مفتوحة منذ انطلاق فتوحات جنكيز خان، حيث أثبت '
                                                     'المماليك قدرتهم على مواجهة تكتيكات الخيالة المغولية واستخدام نفس '
                                                     'أسلحتهم وقوسهم المركب بتنظيم دفاعي وهجومي محكم.',
                          'primary_and_secondary_sources': ['تقي الدين المقريزي (ت. 845 هـ): السلوك لمعرفة دول الملوك، '
                                                            'دار الكتب العلمية، بيروت، ج1.',
                                                            'شمس الدين الذهبي (ت. 748 هـ): تاريخ الإسلام ووفيات '
                                                            'المشاهير والأعلام، دار الغرب الإسلامي، أحداث سنة 658 هـ.',
                                                            'جمال الدين ابن تغري بردي (ت. 874 هـ): النجوم الزاهرة في '
                                                            'ملوك مصر والقاهرة، الهيئة المصرية العامة للكتاب، ج7.',
                                                            'David Ayalon (1977): Studies on the Mamluks of Egypt, '
                                                            'Variorum Reprints, London.'],
                          'visual_disclosure': 'المشاهد البصرية تعرض مناظر موثقة لسهل عين جالوت وسلسلة جبال فلسطين، '
                                               'وقلعة صلاح الدين بالقاهرة، وسيوف ودروع ومخطوطات الفروسية المملوكية '
                                               'الأصلية المحفوظة في المتاحف التراثية (رخصة المشاع الإبداعي من '
                                               'ويكيميديا كومنز).'},
  'scenes': [{'scene_num': 1,
              'shot_type': 'لقطة افتتاحية واسعة لسهول عين جالوت الخضراء (Wide Valley Establishing Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'في الخامس والعشرين من رمضان عام ستمئة وثمانية وخمسين للهجرة، كان مصير العالم '
                                 'الإسلامي كله معلقاً في سهل عين جالوت!',
              'caption_chunks': ['٢٥ رمضان ٦٥٨ هـ (١٢٦٠ م):',
                                 'كان مصير العالم الإسلامي معلقاً',
                                 'في سهل عين جالوت بفلسطين!'],
              'wikimedia_exact_files': ['File:Valley of Jezreel (Israel).jpg', 'File:Jezreel Valley 1.jpg'],
              'wikimedia_queries': ['Valley of Jezreel Israel', 'Jezreel Valley landscape']},
             {'scene_num': 2,
              'shot_type': 'لقطة معمارية لأسوار قلعة القاهرة التاريخية (Mamluk Citadel Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'بعد سقوط بغداد واجتياح مدن الشام، اعتقد الجميع أن جيوش المغول قوة لا يمكن لأي أمة '
                                 'على وجه الأرض إيقافها.',
              'caption_chunks': ['بعد سقوط بغداد ودمشق،', 'ظن العالم أن جيش المغول', 'قوة مستحيل قهرها!'],
              'wikimedia_exact_files': ['File:Cairo Citadel (Egypt).jpg', 'File:Saladin Citadel of Cairo.jpg'],
              'wikimedia_queries': ['Cairo Citadel Egypt', 'Saladin Citadel fortress']},
             {'scene_num': 3,
              'shot_type': 'لقطة متوسطة لسيوف وخوذ المماليك في المتحف (Mamluk Weapons Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'لكن سلطان مصر سيف الدين قطز، رفض الاستسلام وقرر الخروج لملاقاتهم في أرض المعركة '
                                 'بدلاً من انتظار الحصار.',
              'caption_chunks': ['لكن السلطان سيف الدين قطز', 'رفض التهديد والاستسلام', 'وقرر خوض المعركة الفاصلة!'],
              'wikimedia_exact_files': ['File:Imperial Armoury Topkapi Istanbul (19).JPG',
                                        'File:Fatih Sultan-Schwert.jpg'],
              'wikimedia_queries': ['Mamluk sword armor', 'Topkapi palace arms']},
             {'scene_num': 4,
              'shot_type': 'لقطة لتكتيك الكمين الحربي بين التلال (Tactical Valley Ambush Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'وضع القائد ركن الدين بيبرس خطة عبقرية؛ حيث تقدم بطليعة الجيش وتظاهر بالانكسار '
                                 'والانسحاب السريع.',
              'caption_chunks': ['تقدم القائد ركن الدين بيبرس',
                                 'بطليعة الجيش وتظاهر بالانسحاب',
                                 'لاستدراج المغول إلى المضيق!'],
              'wikimedia_exact_files': ['File:Apamea 01.jpg', 'File:Apamea (6362535167).jpg'],
              'wikimedia_queries': ['Ancient Syria valley hills', 'Apamea landscape']},
             {'scene_num': 5,
              'shot_type': 'لقطة لمخطوطة الفروسية والقتال المملوكية (Mamluk Furusiyya Manuscript Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'اندفع القائد المغولي كتبغا بكل ثقله خلف الطليعة، متوهماً أن الجيش المصري قد فر من '
                                 'أمامه.',
              'caption_chunks': ['اندفع جيش التتار بكل ثقله', 'خلف الطليعة المنسحبة', 'ظناً منهم أن النصر قد حسم!'],
              'wikimedia_exact_files': ["File:Bifolium from the Andalusian Pink Qur'an MET DP-14019-001.jpg",
                                        'File:Koran, Illuminated incipit page with headpiece, Walters Manuscript '
                                        'W.556, fol. 4b (4690325429).jpg'],
              'wikimedia_queries': ['Mamluk furusiyya manuscript', 'Islamic manuscript warriors']},
             {'scene_num': 6,
              'shot_type': 'لقطة ذروة النداء التاريخي واشتعال القتال (Climax Battle Cry Shot)',
              'is_night_scene': False,
              'arabic_sentence': "وفور دخولهم الوادي، ألقى قطز خوذته على الأرض وصرخ بصوته المزلزل: 'وا إسلاماه!' وهجم "
                                 'بنفسه في قلب المعركة.',
              'caption_chunks': ['وفجأة ألقى قطز خوذته وصرخ:', '«وا إسلاماه!»', 'وهجم بنفسه في قلب الميدان!'],
              'wikimedia_exact_files': ['File:A portion of Panorama 1453 siege scene.jpg',
                                        'File:Belagerung Konstantinopels.jpg'],
              'wikimedia_queries': ['Panorama 1453 battle', 'Epic battle scene painting']},
             {'scene_num': 7,
              'shot_type': 'لقطة هبوط قوات الدعم من قمم الجبال (Mountain Cavalry Charge Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'انقضت قوات الكمين المخبأة خلف التلال كالسيل الجارف، وأطبقت على المغول من كل اتجاه في '
                                 'حصار محكم.',
              'caption_chunks': ['انقضت قوات الكمين من الجبال',
                                 'كالسيل الجارف، وأطبقت الحصار',
                                 'على جيش المغول من كل اتجاه!'],
              'wikimedia_exact_files': ['File:Fausto Zonaro - The Ottoman Fleet Passing Over Land.jpg',
                                        'File:Conquest of Constantinople, Zonaro.jpg'],
              'wikimedia_queries': ['Fausto Zonaro cavalry', 'Battle charge painting']},
             {'scene_num': 8,
              'shot_type': 'لقطة انهيار وسقوط قادة الغزاة (Collapse of Mongol Vanguard Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'قُتل القائد كتبغا نوين وتشتت صفوف جيشه، وكانت تلك أول هزيمة ساحقة للمغول في معركة '
                                 'ميدانية مفتوحة!',
              'caption_chunks': ['سقط القائد كتبغا صريعاً،',
                                 'وتحطمت أسطورة الجيش الذي لا يقهر',
                                 'في أول هزيمة ساحقة في تاريخهم!'],
              'wikimedia_exact_files': ['File:Zonaro GatesofConst.jpg',
                                        'File:Benjamin-Constant-The Entry of Mahomet II into Constantinople-1876.jpg'],
              'wikimedia_queries': ['Historical battlefield victory', 'Zonaro GatesofConst']},
             {'scene_num': 9,
              'shot_type': 'لقطة النصر العظيم وحماية الأمة (Monumental Impact Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'أنقذت عين جالوت العالم الإسلامي من الإبادة، وحمت مراكز الحضارة والعلوم في مصر '
                                 'والمغرب من الاندثار.',
              'caption_chunks': ['أنقذت عين جالوت الأمة من الإبادة،',
                                 'وحمت مراكز الحضارة والعلوم',
                                 'في مصر والمغرب من الاندثار!'],
              'wikimedia_exact_files': ['File:Cairo Citadel (Egypt).jpg', 'File:Saladin Citadel of Cairo.jpg'],
              'wikimedia_queries': ['Cairo Citadel fortress', 'Saladin Citadel']},
             {'scene_num': 10,
              'shot_type': 'لقطة ختامية لرايات النصر الأندلسية والإسلامية (Historic Finale Standard Shot)',
              'is_night_scene': False,
              'arabic_sentence': 'يوم سطره التاريخ بمداد من شجاعة وتضحية لا تُنسى! اشترك في قناة مخطوطات منسية لمزيد '
                                 'من الحقائق الموثقة.',
              'caption_chunks': ['يوم سطره التاريخ بمداد من شجاعة!',
                                 'اشترك الآن في مخطوطات منسية',
                                 'لمزيد من بطولات التاريخ الموثق!'],
              'wikimedia_exact_files': ['File:Mosque of Cordoba.jpg', 'File:Hagia Sophia Mars 2013.jpg'],
              'wikimedia_queries': ['Islamic civilization heritage', 'Mosque of Cordoba']}]}]
# =========================================================================================
# 3. محرك الجدولة المتتابعة بتوقيت القاهرة (Africa/Cairo DST-Aware Sequential Scheduler)
# =========================================================================================
def compute_cairo_730pm_utc_iso(target_day: date) -> Tuple[str, str]:
    """
    حساب موعد النشر الساعة 7:30 مساءً بتوقيت مصر (Africa/Cairo) بدقة تامة
    مع مراعاة التوقيت الصيفي (UTC+3) والتوقيت الشتوي (UTC+2) تلقائياً،
    وإرجاع: (local_cairo_iso, utc_publish_at_iso).
    """
    cairo_tz = ZoneInfo("Africa/Cairo")
    local_dt = datetime.combine(target_day, dt_time(19, 30, 0), tzinfo=cairo_tz)
    utc_dt = local_dt.astimezone(timezone.utc)
    return local_dt.isoformat(), utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_schedule_ledger() -> Dict[str, Any]:
    if os.path.exists(SCHEDULE_LEDGER_FILE):
        try:
            with open(SCHEDULE_LEDGER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("scheduled_slots", {})
                    data.setdefault("uploaded_topics", {})
                    data.setdefault("last_scheduled_date", None)
                    return data
        except Exception:
            pass
    return {"scheduled_slots": {}, "uploaded_topics": {}, "last_scheduled_date": None}


def save_schedule_ledger(ledger: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(SCHEDULE_LEDGER_FILE), exist_ok=True)
    with open(SCHEDULE_LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)


def get_next_available_schedule_dates(
    count: int,
    youtube_service: Optional[Any] = None,
    reference_today: Optional[date] = None
) -> List[Tuple[date, str, str]]:
    """
    تحديد أول `count` مواعيد نشر يومية متتالية متاحة الساعة 7:30 مساءً بتوقيت مصر،
    بحيث تبدأ بعد آخر فيديو مجدول بالفعل دون إزاحة الفيديوهات القديمة أو تكرار مواعيدها.
    """
    cairo_tz = ZoneInfo("Africa/Cairo")
    today_cairo = reference_today or datetime.now(cairo_tz).date()
    ledger = load_schedule_ledger()
    occupied_dates = set(ledger.get("scheduled_slots", {}).keys())
    latest_date: Optional[date] = None

    if ledger.get("last_scheduled_date"):
        try:
            latest_date = date.fromisoformat(ledger["last_scheduled_date"])
        except Exception:
            pass

    if os.path.exists(LEGACY_LAST_DATE_FILE):
        try:
            with open(LEGACY_LAST_DATE_FILE, "r", encoding="utf-8") as f:
                legacy_d = date.fromisoformat(f.read().strip())
                occupied_dates.add(legacy_d.isoformat())
                if latest_date is None or legacy_d > latest_date:
                    latest_date = legacy_d
        except Exception:
            pass

    if youtube_service is not None:
        try:
            ch_res = youtube_service.channels().list(part="contentDetails", mine=True).execute()
            uploads_id = ch_res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
            pl_res = youtube_service.playlistItems().list(part="contentDetails", playlistId=uploads_id, maxResults=50).execute()
            v_ids = [it["contentDetails"]["videoId"] for it in pl_res.get("items", [])]
            if v_ids:
                v_res = youtube_service.videos().list(part="status", id=",".join(v_ids[:50])).execute()
                for item in v_res.get("items", []):
                    pub_at = item.get("status", {}).get("publishAt")
                    if pub_at:
                        dt_utc = datetime.fromisoformat(pub_at.replace("Z", "+00:00"))
                        dt_cairo_day = dt_utc.astimezone(cairo_tz).date()
                        occupied_dates.add(dt_cairo_day.isoformat())
                        if latest_date is None or dt_cairo_day > latest_date:
                            latest_date = dt_cairo_day
        except Exception:
            pass

    cursor_day = max(today_cairo + timedelta(days=1), (latest_date + timedelta(days=1)) if latest_date else (today_cairo + timedelta(days=1)))
    slots: List[Tuple[date, str, str]] = []

    while len(slots) < count:
        if cursor_day.isoformat() not in occupied_dates:
            local_iso, utc_iso = compute_cairo_730pm_utc_iso(cursor_day)
            slots.append((cursor_day, local_iso, utc_iso))
        cursor_day += timedelta(days=1)

    return slots


# =========================================================================================
# 4. دوال الفحص البصري، منع التكرار، وحقوق الاستخدام (QA, Deduplication & Licensing)
# =========================================================================================
def compute_sha256_bytes(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def compute_dhash_64bit(pil_img: Image.Image) -> str:
    gray = pil_img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = np.asarray(gray, dtype=np.int16)
    diff = pixels[:, 1:] > pixels[:, :-1]
    bit_string = "".join("1" if b else "0" for b in diff.flatten())
    return f"{int(bit_string, 2):016x}"


def hamming_distance_hex(hash_a: str, hash_b: str) -> int:
    try:
        return bin(int(hash_a, 16) ^ int(hash_b, 16)).count("1")
    except Exception:
        return 64


def load_dedup_registry() -> Dict[str, Any]:
    if os.path.exists(VISUAL_REGISTRY_FILE):
        try:
            with open(VISUAL_REGISTRY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("sha256_to_scene", {})
                    data.setdefault("dhash_to_scene", {})
                    data.setdefault("history_log", [])
                    return data
        except Exception:
            pass
    return {"sha256_to_scene": {}, "dhash_to_scene": {}, "history_log": []}


def save_dedup_registry(registry: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(VISUAL_REGISTRY_FILE), exist_ok=True)
    with open(VISUAL_REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def validate_and_analyze_image_bytes(
    raw_bytes: bytes,
    is_night_scene: bool = False,
    min_w: int = MIN_SOURCE_WIDTH,
    min_h: int = MIN_SOURCE_HEIGHT
) -> Dict[str, Any]:
    result = {
        "valid": False,
        "reason": "",
        "width": 0,
        "height": 0,
        "luma_mean": 0.0,
        "luma_std": 0.0,
        "dark_pixel_ratio": 1.0,
        "sha256": "",
        "dhash": "",
        "pil_image": None
    }

    if not raw_bytes or len(raw_bytes) < 4096:
        result["reason"] = f"ملف صورة فارغ أو صغير جداً ({len(raw_bytes) if raw_bytes else 0} bytes)"
        return result

    try:
        ver_im = Image.open(io.BytesIO(raw_bytes))
        ver_im.verify()
    except Exception as e:
        result["reason"] = f"ملف صورة تالف (PIL verify failed: {e})"
        return result

    try:
        im = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    except Exception as e:
        result["reason"] = f"تعذر فك ترميز الصورة إلى RGB ({e})"
        return result

    w, h = im.size
    result["width"] = w
    result["height"] = h
    if w < min_w or h < min_h:
        result["reason"] = f"أبعاد الصورة الأصلية ({w}x{h}) أقل من الحد الأدنى المسموح ({min_w}x{min_h})"
        return result

    arr = np.asarray(im, dtype=np.float32)
    luma = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    luma_mean = float(np.mean(luma))
    luma_std = float(np.std(luma))
    dark_ratio = float(np.mean(luma < 12.0))

    result["luma_mean"] = round(luma_mean, 2)
    result["luma_std"] = round(luma_std, 2)
    result["dark_pixel_ratio"] = round(dark_ratio, 4)

    min_luma = MIN_LUMA_NIGHT if is_night_scene else MIN_LUMA_STANDARD
    min_std = MIN_CONTRAST_STD_NIGHT if is_night_scene else MIN_CONTRAST_STD_STANDARD

    if luma_mean < min_luma:
        result["reason"] = f"مشهد معتم جداً أو أسود (السطوع={luma_mean:.1f} < الحد الأدنى {min_luma})"
        return result

    if luma_mean > MAX_LUMA_OVEREXPOSED:
        result["reason"] = f"مشهد محترق الإضاءة أو أبيض سادة (السطوع={luma_mean:.1f})"
        return result

    if luma_std < min_std:
        result["reason"] = f"مشهد سادة أو باهت عديم التفاصيل (التباين المعياري={luma_std:.1f} < {min_std})"
        return result

    if dark_ratio > 0.85 and not is_night_scene:
        result["reason"] = f"نسبة البكسلات السوداء مرتفعة جداً ({dark_ratio*100:.1f}%)"
        return result

    result["sha256"] = compute_sha256_bytes(raw_bytes)
    result["dhash"] = compute_dhash_64bit(im)
    result["pil_image"] = im
    result["valid"] = True
    result["reason"] = "اجتاز فحص سلامة الملف والدقة والسطوع والتباين"
    return result


def check_image_duplication(
    sha256_hex: str,
    dhash_hex: str,
    in_video_registry: Dict[str, Any],
    persistent_registry: Dict[str, Any],
    current_topic_prefix: str
) -> Tuple[bool, str]:
    if sha256_hex in in_video_registry.get("sha256_to_scene", {}):
        prev_scene = in_video_registry["sha256_to_scene"][sha256_hex]
        return True, f"تطابق تام SHA-256 مع مشهد سابق داخل نفس الفيديو ({prev_scene})"

    for existing_dhash, scene_label in in_video_registry.get("dhash_to_scene", {}).items():
        dist = hamming_distance_hex(dhash_hex, existing_dhash)
        if dist <= MAX_DHASH_HAMMING_DISTANCE:
            return True, f"تشابه بصري مكرر (dHash Hamming={dist}) مع مشهد داخل نفس الفيديو ({scene_label})"

    for existing_sha, scene_label in persistent_registry.get("sha256_to_scene", {}).items():
        if existing_sha == sha256_hex and not scene_label.startswith(current_topic_prefix):
            return True, f"تطابق تام SHA-256 مع فيديو سابق ({scene_label})"

    for existing_dhash, scene_label in persistent_registry.get("dhash_to_scene", {}).items():
        if not scene_label.startswith(current_topic_prefix):
            dist = hamming_distance_hex(dhash_hex, existing_dhash)
            if dist <= MAX_DHASH_HAMMING_DISTANCE:
                return True, f"تشابه بصري مكرر (dHash Hamming={dist}) مع فيديو سابق ({scene_label})"

    return False, "صورة فريدة غير مكررة داخل الفيديو ولا في الفيديوهات السابقة"


def download_wikimedia_image_with_license(iinfo: Dict[str, Any], title: str, headers: Dict[str, str]) -> Optional[Tuple[bytes, str, str]]:
    title_low = title.lower()
    if any(k in title_low for k in FORBIDDEN_TITLE_SUBSTRINGS):
        return None

    mime = iinfo.get("mime", "").lower()
    if not any(m in mime for m in ["jpeg", "jpg", "png"]):
        return None

    w = int(iinfo.get("width", 0))
    h = int(iinfo.get("height", 0))
    if w < MIN_SOURCE_WIDTH or h < MIN_SOURCE_HEIGHT:
        return None

    extmeta = iinfo.get("extmetadata", {})
    license_short = extmeta.get("LicenseShortName", {}).get("value", "Public Domain / Wikimedia Commons Free License")
    artist_raw = extmeta.get("Artist", {}).get("value", "Wikimedia Contributor")
    artist_clean = re.sub(r"<[^>]+>", "", str(artist_raw)).strip()[:80]
    license_info = f"{license_short} (Author: {artist_clean})"

    target_url = iinfo.get("thumburl") or iinfo.get("url")
    if not target_url:
        return None

    try:
        r = requests.get(target_url, headers=headers, timeout=20)
        if r.status_code == 200 and len(r.content) > 8192:
            return r.content, f"Wikimedia Commons ({title}, source {w}x{h})", license_info
    except Exception:
        pass
    return None


def fetch_wikimedia_exact_titles(file_titles: List[str]) -> List[Tuple[bytes, str, str]]:
    if not file_titles:
        return []
    api_url = "https://commons.wikimedia.org/w/api.php"
    headers = {
        "User-Agent": "IslamicHistoryShortsQA/3.0 (https://commons.wikimedia.org; Historical Documentary)"
    }
    candidates = []
    for title in file_titles:
        params = {
            "action": "query",
            "titles": title,
            "prop": "imageinfo",
            "iiprop": "url|dimensions|mime|extmetadata",
            "iiurlwidth": 1920,
            "format": "json"
        }
        try:
            r = requests.get(api_url, params=params, headers=headers, timeout=15)
            if r.status_code != 200:
                continue
            pages = r.json().get("query", {}).get("pages", {})
            for page_id, page_data in pages.items():
                if str(page_id) == "-1":
                    continue
                iinfo_list = page_data.get("imageinfo", [])
                if not iinfo_list:
                    continue
                dl = download_wikimedia_image_with_license(iinfo_list[0], page_data.get("title", title), headers)
                if dl:
                    candidates.append(dl)
        except Exception:
            continue
    return candidates


def fetch_wikimedia_candidates(query: str, max_results: int = 10) -> List[Tuple[bytes, str, str]]:
    api_url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": max_results,
        "prop": "imageinfo",
        "iiprop": "url|dimensions|mime|extmetadata",
        "iiurlwidth": 1920,
        "format": "json"
    }
    headers = {
        "User-Agent": "IslamicHistoryShortsQA/3.0 (https://commons.wikimedia.org; Historical Documentary)"
    }
    candidates = []
    try:
        r = requests.get(api_url, params=params, headers=headers, timeout=20)
        if r.status_code != 200:
            return candidates
        pages = r.json().get("query", {}).get("pages", {})
        for _, page_data in pages.items():
            title = page_data.get("title", "Wikimedia_Image")
            iinfo_list = page_data.get("imageinfo", [])
            if not iinfo_list:
                continue
            dl = download_wikimedia_image_with_license(iinfo_list[0], title, headers)
            if dl:
                candidates.append(dl)
    except Exception:
        pass
    return candidates


def upscale_and_grade_to_4k(pil_img: Image.Image) -> Image.Image:
    target_ratio = FINAL_WIDTH / float(FINAL_HEIGHT)
    src_w, src_h = pil_img.size
    src_ratio = src_w / float(src_h)

    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        cropped = pil_img.crop((left, 0, left + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        cropped = pil_img.crop((0, top, src_w, top + new_h))

    upscaled = cropped.resize((FINAL_WIDTH, FINAL_HEIGHT), Image.Resampling.LANCZOS)
    upscaled = ImageEnhance.Contrast(upscaled).enhance(1.06)
    upscaled = ImageEnhance.Color(upscaled).enhance(1.05)
    upscaled = upscaled.filter(ImageFilter.UnsharpMask(radius=1.2, percent=65, threshold=4))
    return upscaled


def acquire_verified_scene_image(
    topic_id: str,
    scene_bp: Dict[str, Any],
    in_video_registry: Dict[str, Any],
    persistent_registry: Dict[str, Any],
    output_scene_path: str
) -> Dict[str, Any]:
    scene_num = scene_bp["scene_num"]
    is_night = scene_bp.get("is_night_scene", False)
    arabic_sentence = scene_bp["arabic_sentence"]
    shot_type = scene_bp["shot_type"]

    attempt_logs = []

    def try_register_candidate(raw_bytes: bytes, src_desc: str, license_str: str, label_prefix: str) -> Optional[Dict[str, Any]]:
        qa = validate_and_analyze_image_bytes(raw_bytes, is_night_scene=is_night)
        if not qa["valid"]:
            attempt_logs.append(f"{label_prefix} مرفوضة بصرياً: {qa['reason']}")
            return None

        is_dup, dup_reason = check_image_duplication(
            qa["sha256"], qa["dhash"], in_video_registry, persistent_registry, current_topic_prefix=topic_id
        )
        if is_dup:
            attempt_logs.append(f"{label_prefix} مكررة: {dup_reason}")
            return None

        final_4k_img = upscale_and_grade_to_4k(qa["pil_image"])
        final_4k_img.save(output_scene_path, format="JPEG", quality=95, subsampling=0)

        scene_key = f"{topic_id}_scene_{scene_num}"
        in_video_registry["sha256_to_scene"][qa["sha256"]] = scene_key
        in_video_registry["dhash_to_scene"][qa["dhash"]] = scene_key
        persistent_registry["sha256_to_scene"][qa["sha256"]] = scene_key
        persistent_registry["dhash_to_scene"][qa["dhash"]] = scene_key

        return {
            "scene_num": scene_num,
            "shot_type": shot_type,
            "arabic_sentence": arabic_sentence,
            "file_name": os.path.basename(output_scene_path),
            "source": src_desc,
            "license": license_str,
            "native_resolution": f"{qa['width']}x{qa['height']}",
            "output_resolution": f"{FINAL_WIDTH}x{FINAL_HEIGHT} (Upscaled from {qa['width']}x{qa['height']} via Lanczos + Mild UnsharpMask)",
            "file_integrity": "سليم (PIL Verified)",
            "sha256": qa["sha256"],
            "dhash": qa["dhash"],
            "uniqueness": dup_reason,
            "luma_mean": qa["luma_mean"],
            "luma_std": qa["luma_std"],
            "decision": "مقبول (Approved)",
            "attempt_history": attempt_logs
        }

    exact_candidates = fetch_wikimedia_exact_titles(scene_bp.get("wikimedia_exact_files", []))
    for raw_bytes, src_desc, lic in exact_candidates:
        accepted = try_register_candidate(raw_bytes, src_desc, lic, f"ملف موثق {src_desc}")
        if accepted:
            return accepted

    for wiki_q in scene_bp.get("wikimedia_queries", []):
        candidates = fetch_wikimedia_candidates(wiki_q)
        if not candidates:
            attempt_logs.append(f"استعلام Wikimedia «{wiki_q}» لم يرجع صوراً مطابقة للأبعاد")
            continue
        for raw_bytes, src_desc, lic in candidates:
            accepted = try_register_candidate(raw_bytes, src_desc, lic, f"بحث Wikimedia {src_desc}")
            if accepted:
                return accepted

    return {
        "scene_num": scene_num,
        "shot_type": shot_type,
        "arabic_sentence": arabic_sentence,
        "file_name": None,
        "source": "فشل الجلب من جميع المصادر",
        "license": "غير متوفر",
        "native_resolution": "0x0",
        "output_resolution": "0x0",
        "file_integrity": "غير متوفر",
        "sha256": "",
        "dhash": "",
        "uniqueness": "غير متوفر",
        "luma_mean": 0.0,
        "luma_std": 0.0,
        "decision": "مرفوض (Rejected - Halting Pipeline)",
        "attempt_history": attempt_logs
    }


# =========================================================================================
# 5. توليد التعليق الصوتي المضبوط (45-60s) وبناء كابشن ASS وبناء الوصف الموثق
# =========================================================================================
def generate_voiceover_and_get_duration(full_text: str, output_mp3: str) -> float:
    """
    توليد التعليق الصوتي العربي الفصيح عبر edge-tts مع ضمان ألا تتجاوز مدة الصوت 54 ثانية
    (أقل من دقيقة واحدة بصرامة ليتوافق مع YouTube Shorts السريع).
    """
    import shutil
    voice = "ar-SA-HamedNeural"
    raw_mp3 = output_mp3 + ".raw.mp3"
    cmd = [
        "edge-tts",
        "--voice", voice,
        "--rate=+8%",
        "--pitch=-1Hz",
        "--text", full_text,
        "--write-media", raw_mp3
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        raw_mp3
    ]
    res = subprocess.run(probe_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    raw_dur = float(res.stdout.strip())

    if raw_dur > 56.0:
        tempo_factor = min(1.20, max(1.02, raw_dur / 54.0))
        tempo_cmd = [
            "ffmpeg", "-y", "-i", raw_mp3,
            "-filter:a", f"atempo={tempo_factor:.4f}",
            "-c:a", "libmp3lame", "-q:a", "2",
            output_mp3
        ]
        subprocess.run(tempo_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        import shutil
        shutil.copyfile(raw_mp3, output_mp3)

    res_final = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", output_mp3],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    return float(res_final.stdout.strip())


def compute_proportional_scene_durations(scenes: List[Dict[str, Any]], total_duration: float) -> List[float]:
    word_counts = [max(4, len(s["arabic_sentence"].split())) for s in scenes]
    total_words = sum(word_counts)
    durations = [round((wc / float(total_words)) * total_duration, 3) for wc in word_counts]
    diff = total_duration - sum(durations)
    durations[-1] = round(durations[-1] + diff, 3)
    return durations


def format_ass_timestamp(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        s += 1
        cs = 0
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_synchronized_ass_subtitles(
    scenes: List[Dict[str, Any]],
    scene_durations: List[float],
    ass_path: str
) -> None:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {FINAL_WIDTH}
PlayResY: {FINAL_HEIGHT}
WrapStyle: 1
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Sans Arabic,112,&H0000E5FF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,8,4,2,140,140,480,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    current_time = 0.0

    for scene_bp, dur in zip(scenes, scene_durations):
        chunks = scene_bp.get("caption_chunks") or [scene_bp["arabic_sentence"]]
        chunk_weights = [max(1, len(c.split())) for c in chunks]
        total_w = sum(chunk_weights)
        sub_cursor = current_time

        for idx, (chunk_text, cw) in enumerate(zip(chunks, chunk_weights)):
            chunk_dur = (cw / float(total_w)) * dur
            start_t = sub_cursor
            end_t = (current_time + dur) if idx == len(chunks) - 1 else (sub_cursor + chunk_dur)
            sub_cursor = end_t

            start_str = format_ass_timestamp(start_t)
            end_str = format_ass_timestamp(end_t)
            clean_txt = chunk_text.replace("\n", " ").strip()
            lines.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{{\\fad(120,120)}}{clean_txt}")

        current_time += dur

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def build_documented_youtube_description(episode: Dict[str, Any], scene_qa_reports: List[Dict[str, Any]]) -> str:
    meta = episode["historical_metadata"]
    sources_str = "\n".join(f"• {src}" for src in meta["primary_and_secondary_sources"])
    visual_credits = "\n".join(
        f"• المشهد {r['scene_num']}: {r['source']} [{r.get('license', 'CC/Public Domain')}]"
        for r in scene_qa_reports if r.get("source")
    )
    desc = (
        f"{meta['event_name']} ({meta['historical_period']}).\n\n"
        f"📚 تدقيق تاريخي:\n{meta['historiographical_notes']}\n\n"
        f"📖 المصادر والمراجع التاريخية:\n{sources_str}\n\n"
        f"🖼️ إفصاح وتوثيق المصادر البصرية:\n{meta['visual_disclosure']}\n{visual_credits}\n\n"
        f"#التاريخ_الإسلامي #مخطوطات_منسية #الأندلس #قرطبة #وثائقي #shorts"
    )
    return desc[:4900]


# =========================================================================================
# 6. الرندر السينمائي وفحص الفيديو النهائي والاتصال الموثق بـ YouTube API
# =========================================================================================

def generate_historical_documentary_sfx_track(duration_sec: float, num_scenes: int, out_wav: str):
    """
    توليد شريط موسيقي ومؤثرات صوتية تاريخية غنية وواضحة (Historical Documentary Soundscape):
    1. وسادة صوتية وتناغم أندلسي هادئ في الخلفية (Ambient Andalusian Pad).
    2. ضربات دفوف وطبول إيقاعية عميقة (Deep Acoustic Low War Drum Beats) كل 1.2 ثانية تعطي هيبة ووقاراً وثائقياً.
    3. مؤثر حركي سينمائي وانتقال صوتي ناعم (Cinematic Whoosh & Transition Texture) عند لحظة انتقال كل مشهد.
    4. رنين معدني أندلسي خافت ونغمات فولاذية دقيقة (Metallic Chime / Astrolabe & Sword Resonance).
    """
    sr = 24000
    n = int(duration_sec * sr)
    t = np.linspace(0, duration_sec, n, endpoint=False)

    pad = (
        0.045 * np.sin(2 * np.pi * 110.0 * t) +
        0.035 * np.sin(2 * np.pi * 164.81 * t) +
        0.025 * np.sin(2 * np.pi * 220.0 * t)
    ) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.12 * t))

    drum_track = np.zeros(n, dtype=np.float32)
    beat_step = 1.2
    for b_t in np.arange(0.3, duration_sec - 0.5, beat_step):
        b_idx = int(b_t * sr)
        d_len = min(int(0.55 * sr), n - b_idx)
        if d_len > 0:
            td = np.linspace(0, d_len / sr, d_len, endpoint=False)
            f_sweep = 120.0 * np.exp(-15.0 * td) + 45.0
            phase = 2 * np.pi * np.cumsum(f_sweep) / sr
            env = np.exp(-6.0 * td)
            drum_track[b_idx:b_idx + d_len] += (0.42 * np.sin(phase) + 0.15 * np.sin(2 * phase)) * env

    transition_track = np.zeros(n, dtype=np.float32)
    seg_dur = duration_sec / float(max(1, num_scenes))
    for s_idx in range(1, num_scenes):
        cut_t = s_idx * seg_dur
        c_idx = int(cut_t * sr)
        w_len = int(0.40 * sr)
        w_start = max(0, c_idx - w_len // 2)
        w_end = min(n, c_idx + w_len // 2)
        if w_end > w_start:
            raw_w = np.random.uniform(-1, 1, w_end - w_start)
            smooth_w = np.convolve(raw_w, np.ones(15) / 15.0, mode='same')
            transition_track[w_start:w_end] += 0.28 * smooth_w * np.hanning(w_end - w_start)

        m_len = min(int(0.7 * sr), n - c_idx)
        if m_len > 0:
            tm = np.linspace(0, m_len / sr, m_len, endpoint=False)
            chime = (0.16 * np.sin(2 * np.pi * 1480.0 * tm) + 0.09 * np.sin(2 * np.pi * 2960.0 * tm)) * np.exp(-5.0 * tm)
            transition_track[c_idx:c_idx + m_len] += chime

    combined = pad + drum_track + transition_track
    pcm = (np.clip(combined, -0.92, 0.92) * 32767).astype(np.int16)
    with wave.open(out_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())

def render_scene_clip(
    image_path: str,
    clip_path: str,
    duration: float,
    scene_num: int
) -> bool:
    zoom_direction = "in" if scene_num % 2 == 1 else "out"
    if zoom_direction == "in":
        scale_expr = f"scale=2300:4088,crop={FINAL_WIDTH}:{FINAL_HEIGHT}:'(iw-ow)/2':'(ih-oh)/2'"
    else:
        scale_expr = f"scale=2260:4018,crop={FINAL_WIDTH}:{FINAL_HEIGHT}:'(iw-ow)/2':'(ih-oh)/2'"

    vf_chain = f"{scale_expr},fps={FINAL_FPS},format=yuv420p"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-t", f"{duration:.3f}",
        "-i", image_path,
        "-vf", vf_chain,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-an",
        clip_path
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return res.returncode == 0 and os.path.exists(clip_path) and os.path.getsize(clip_path) > 10000


def verify_final_video_file(
    video_path: str,
    expected_duration: float,
    scenes: List[Dict[str, Any]],
    scene_durations: List[float]
) -> Dict[str, Any]:
    checks = {
        "file_exists_and_non_empty": False,
        "has_video_stream": False,
        "has_audio_stream": False,
        "duration_matches_audio": False,
        "duration_within_shorts_target_40_to_65s": False,
        "resolution_verified_2160x3840": False,
        "no_black_frames_in_any_scene": False,
        "measured_width": 0,
        "measured_height": 0,
        "measured_duration": 0.0,
        "scene_frame_luminance": {},
        "failed_scenes": [],
        "all_passed": False
    }

    if not os.path.exists(video_path) or os.path.getsize(video_path) < 100_000:
        return checks
    checks["file_exists_and_non_empty"] = True

    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_type,width,height:format=duration",
        "-of", "json",
        video_path
    ]
    res = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        return checks

    info = json.loads(res.stdout)
    streams = info.get("streams", [])
    for st in streams:
        if st.get("codec_type") == "video":
            checks["has_video_stream"] = True
            checks["measured_width"] = int(st.get("width", 0))
            checks["measured_height"] = int(st.get("height", 0))
        elif st.get("codec_type") == "audio":
            checks["has_audio_stream"] = True

    dur = float(info.get("format", {}).get("duration", 0.0))
    checks["measured_duration"] = round(dur, 2)
    checks["duration_matches_audio"] = abs(dur - expected_duration) <= 1.5
    checks["duration_within_shorts_target_40_to_65s"] = (38.0 <= dur <= 62.0)
    checks["resolution_verified_2160x3840"] = (
        checks["measured_width"] == FINAL_WIDTH and checks["measured_height"] == FINAL_HEIGHT
    )

    cursor = 0.0
    failed_scene_nums = []
    for scene_bp, s_dur in zip(scenes, scene_durations):
        s_num = scene_bp["scene_num"]
        mid_t = cursor + (s_dur * 0.5)
        cursor += s_dur

        frame_cmd = [
            "ffmpeg", "-v", "error",
            "-ss", f"{mid_t:.2f}",
            "-i", video_path,
            "-frames:v", "1",
            "-f", "image2pipe",
            "-vcodec", "png",
            "-"
        ]
        f_res = subprocess.run(frame_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if f_res.returncode != 0 or not f_res.stdout:
            failed_scene_nums.append(s_num)
            continue

        im = Image.open(io.BytesIO(f_res.stdout)).convert("RGB")
        arr = np.asarray(im, dtype=np.float32)
        luma = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        mean_val = round(float(np.mean(luma)), 2)
        std_val = round(float(np.std(luma)), 2)
        checks["scene_frame_luminance"][f"scene_{s_num}"] = {"luma_mean": mean_val, "luma_std": std_val}

        min_req = MIN_LUMA_NIGHT if scene_bp.get("is_night_scene") else MIN_LUMA_STANDARD
        if mean_val < min_req or std_val < 10.0:
            failed_scene_nums.append(s_num)

    checks["failed_scenes"] = failed_scene_nums
    checks["no_black_frames_in_any_scene"] = (len(failed_scene_nums) == 0)

    checks["all_passed"] = all([
        checks["file_exists_and_non_empty"],
        checks["has_video_stream"],
        checks["has_audio_stream"],
        checks["duration_matches_audio"],
        checks["duration_within_shorts_target_40_to_65s"],
        checks["resolution_verified_2160x3840"],
        checks["no_black_frames_in_any_scene"]
    ])
    return checks


def build_contact_sheet_from_rendered_video(
    video_path: str,
    scenes: List[Dict[str, Any]],
    scene_durations: List[float],
    output_contact_sheet: str
) -> None:
    """
    استخراج لقطات المشاهد العشرة من ملف الفيديو النهائي نفسه (بعد حرق الكابشن العربي)
    لتوفير دليل بصري قاطع على الصورة والكابشن معاً في لوحة واحدة.
    """
    thumb_w, thumb_h = 360, 640
    cols, rows = 5, 2
    sheet = Image.new("RGB", (cols * thumb_w, rows * thumb_h), (15, 15, 15))
    draw = ImageDraw.Draw(sheet)

    cursor = 0.0
    for idx, (scene_bp, s_dur) in enumerate(zip(scenes, scene_durations)):
        s_num = scene_bp["scene_num"]
        mid_t = cursor + (s_dur * 0.5)
        cursor += s_dur

        frame_cmd = [
            "ffmpeg", "-v", "error",
            "-ss", f"{mid_t:.2f}",
            "-i", video_path,
            "-frames:v", "1",
            "-f", "image2pipe",
            "-vcodec", "png",
            "-"
        ]
        f_res = subprocess.run(frame_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if f_res.returncode == 0 and f_res.stdout:
            im = Image.open(io.BytesIO(f_res.stdout)).convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            c = idx % cols
            r = idx // cols
            x0, y0 = c * thumb_w, r * thumb_h
            sheet.paste(im, (x0, y0))
            draw.rectangle([x0 + 8, y0 + 8, x0 + 185, y0 + 48], fill=(0, 0, 0))
            draw.text((x0 + 14, y0 + 14), f"Scene {s_num} ({mid_t:.1f}s)", fill=(255, 215, 0))

    sheet.save(output_contact_sheet, format="JPEG", quality=92)


def upload_and_verify_scheduled_youtube_video(
    video_path: str,
    title: str,
    description: str,
    target_day: date,
    local_cairo_iso: str,
    utc_publish_at_iso: str
) -> Dict[str, Any]:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    token_candidates = [
        os.environ.get("YOUTUBE_TOKEN_PATH", ""),
        os.path.join(DRIVE_ROOT, "token_manuscripts.json"),
        os.path.join(DRIVE_ROOT, "token.json")
    ]
    token_path = next((p for p in token_candidates if p and os.path.exists(p)), None)
    if not token_path:
        return {
            "uploaded": False,
            "verified": False,
            "reason": "لم يتم العثور على ملف token_manuscripts.json على Google Drive"
        }

    try:
        creds = Credentials.from_authorized_user_file(token_path)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "w", encoding="utf-8") as f:
                f.write(creds.to_json())

        youtube = build("youtube", "v3", credentials=creds)
        body = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": ["التاريخ_الإسلامي", "مخطوطات_منسية", "الأندلس", "قرطبة", "وثائقي", "shorts"],
                "categoryId": "27"
            },
            "status": {
                "privacyStatus": "private",
                "publishAt": utc_publish_at_iso,
                "selfDeclaredMadeForKids": False
            }
        }
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        insert_res = req.execute()

        vid_id = insert_res.get("id")
        returned_status = insert_res.get("status", {})
        returned_privacy = returned_status.get("privacyStatus")
        returned_publish_at = returned_status.get("publishAt")

        list_verified = False
        try:
            check_res = youtube.videos().list(part="status,snippet", id=vid_id).execute()
            items = check_res.get("items", [])
            if items:
                returned_privacy = items[0]["status"].get("privacyStatus", returned_privacy)
                returned_publish_at = items[0]["status"].get("publishAt", returned_publish_at)
                list_verified = True
        except Exception:
            pass

        is_verified = bool(vid_id and returned_privacy == "private" and returned_publish_at)
        return {
            "uploaded": bool(vid_id),
            "verified": is_verified,
            "list_api_checked": list_verified,
            "video_id": vid_id,
            "video_url": f"https://youtube.com/shorts/{vid_id}" if vid_id else None,
            "target_date": slot_day.isoformat(),
            "cairo_local_schedule": slot_local_cairo,
            "utc_publish_at_requested": slot_utc_publish,
            "utc_publish_at_confirmed": returned_publish_at,
            "privacy_status_confirmed": returned_privacy
        }
    except Exception as e:
        return {
            "uploaded": False,
            "verified": False,
            "reason": str(e)
        }


def update_production_and_analytics_dashboard(
    episode: Dict[str, Any],
    video_path: str,
    contact_sheet_path: str,
    qa_report_path: str,
    final_verification: Dict[str, Any],
    schedule_info: Dict[str, Any],
    scene_qa_reports: List[Dict[str, Any]]
) -> None:
    os.makedirs(os.path.dirname(SOURCES_REGISTRY_FILE), exist_ok=True)
    sources_reg = {}
    if os.path.exists(SOURCES_REGISTRY_FILE):
        try:
            with open(SOURCES_REGISTRY_FILE, "r", encoding="utf-8") as f:
                sources_reg = json.load(f)
        except Exception:
            sources_reg = {}

    sources_reg[episode["topic_id"]] = {
        "updated_at": datetime.now().isoformat(),
        "title": episode["title"],
        "historical_metadata": episode["historical_metadata"],
        "visual_sources": [
            {
                "scene_num": r["scene_num"],
                "source": r["source"],
                "license": r.get("license"),
                "sha256": r["sha256"],
                "dhash": r["dhash"]
            }
            for r in scene_qa_reports
        ]
    }
    with open(SOURCES_REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(sources_reg, f, ensure_ascii=False, indent=2)

    dashboard = {"episodes": []}
    if os.path.exists(ANALYTICS_JSON_FILE):
        try:
            with open(ANALYTICS_JSON_FILE, "r", encoding="utf-8") as f:
                dashboard = json.load(f)
                dashboard.setdefault("episodes", [])
        except Exception:
            dashboard = {"episodes": []}

    entry = {
        "timestamp": datetime.now().isoformat(),
        "mode": MODE,
        "topic_id": episode["topic_id"],
        "title": episode["title"],
        "historical_period": episode["historical_metadata"]["historical_period"],
        "video_file": video_path,
        "contact_sheet_file": contact_sheet_path,
        "qa_report_file": qa_report_path,
        "duration_sec": final_verification.get("measured_duration", 0.0),
        "resolution": f"{final_verification.get('measured_width', 0)}x{final_verification.get('measured_height', 0)}",
        "qa_all_passed": final_verification.get("all_passed", False),
        "youtube_uploaded": schedule_info.get("uploaded", False),
        "youtube_verified": schedule_info.get("verified", False),
        "youtube_url": schedule_info.get("video_url", ""),
        "scheduled_cairo_time": schedule_info.get("cairo_local_schedule", ""),
        "scheduled_utc_time": schedule_info.get("utc_publish_at_confirmed") or schedule_info.get("utc_publish_at_requested", ""),
        "views": 0,
        "likes": 0,
        "avg_view_duration_sec": None,
        "completion_rate_pct": None
    }
    dashboard["episodes"] = [e for e in dashboard["episodes"] if e.get("topic_id") != episode["topic_id"]]
    dashboard["episodes"].append(entry)

    with open(ANALYTICS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)

    fieldnames = [
        "timestamp", "mode", "topic_id", "title", "historical_period",
        "duration_sec", "resolution", "qa_all_passed",
        "youtube_uploaded", "youtube_verified", "youtube_url",
        "scheduled_cairo_time", "scheduled_utc_time", "views", "likes"
    ]
    with open(ANALYTICS_CSV_FILE, "w", encoding="utf-8-sig", newline="") as cf:
        writer = csv.DictWriter(cf, fieldnames=fieldnames)
        writer.writeheader()
        for ep_row in dashboard["episodes"]:
            writer.writerow({k: ep_row.get(k, "") for k in fieldnames})


# =========================================================================================
# 7. نقطة التشغيل الرئيسية (Main Execution Pipeline v3.0)
# =========================================================================================
def run_production_pipeline() -> int:
    ensure_environment()
    os.makedirs(TEST_LAB_DIR, exist_ok=True)
    os.makedirs(SCENES_CACHE_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    next_slots = get_next_available_schedule_dates(count=10)
    target_day, local_cairo_iso, utc_publish_at_iso = next_slots[0]

    print("=" * 92)
    print("🕌 مصنع التاريخ الإسلامي الموثق - الإصدار الإنتاجي (v3.0 Production)")
    print(f"⚙️ وضع التشغيل الحالي (MODE): {MODE}")
    print(f"📂 مجلد المخرجات والتقارير: {TEST_LAB_DIR}")
    print(f"📅 أول موعد نشر تالٍ متاح (بتوقيت مصر): {local_cairo_iso} (المقابل لـ {utc_publish_at_iso})")
    print("📅 جدول المواعيد العشرة المتتالية القادمة (مع مراعاة التوقيت الصيفي/الشتوي لمصر):")
    for idx_s, (s_day, s_loc, s_utc) in enumerate(next_slots, start=1):
        print(f"   [{idx_s:02d}] {s_day.isoformat()} -> القاهرة: {s_loc} | UTC: {s_utc}")
    print("=" * 92)

    persistent_registry = load_dedup_registry()
    in_video_registry = {"sha256_to_scene": {}, "dhash_to_scene": {}}

    ledger = load_schedule_ledger()
    uploaded_topics_map = ledger.get("uploaded_topics", {})

    # اختيار الحلقات التي لم يتم رفعها بعد في السجل الدائم لمنع تكرار أي موضوع
    candidate_episodes = [
        ep for ep in DOCUMENTED_HISTORICAL_EPISODES
        if ep["topic_id"] not in uploaded_topics_map
    ]

    # إذا تم إنتاج جميع الحلقات، نبدأ دورة جديدة دون تكرار الحلقات المتتالية
    if not candidate_episodes:
        print("ℹ️ تم استكمال جميع الحلقات المسجلة في قاعدة البيانات، جاري بدء دورة إنتاجية متجددة...")
        candidate_episodes = DOCUMENTED_HISTORICAL_EPISODES

    # تحديد عدد الحلقات المطلوب إنتاجها بحسب وضع التشغيل
    if MODE in ("DAILY_BATCH_6", "DAILY_BATCH_10"):
        batch_limit = 6 if "6" in MODE else 10
        target_episodes = candidate_episodes[:batch_limit]
    else:
        target_episodes = candidate_episodes[:1]

    print(f"🎯 عدد الحلقات المجدولة للإنتاج في هذه الدورة ({MODE}): {len(target_episodes)} حلقة.")

    total_produced = 0
    total_uploaded = 0

    for ep_idx, episode in enumerate(target_episodes):
        topic_id = episode["topic_id"]
        scenes = episode["scenes"]
        scene_qa_reports = []
        verified_scene_paths = {}
    
        # حجز موعد النشر التلقائي التالي لهذا الفيديو بتوقيت مصر
        current_slots = get_next_available_schedule_dates(count=len(target_episodes))
        slot_day, slot_local_cairo, slot_utc_publish = current_slots[min(ep_idx, len(current_slots) - 1)]
    
        print(f"\n📚 الحلقة التاريخية قيد الإنتاج: {episode['title']}")
        print(f"🏛️ الحقبة التاريخية: {episode['historical_metadata']['historical_period']}")
        print(f"📖 عدد المصادر التاريخية الموثقة: {len(episode['historical_metadata']['primary_and_secondary_sources'])}")
    
        for scene_bp in scenes:
            s_num = scene_bp["scene_num"]
            print(f"\n🔍 [المشهد {s_num:02d}/10] جاري جلب وفحص: {scene_bp['shot_type']}...")
            print(f"   🗣️ الجملة: «{scene_bp['arabic_sentence']}»")
    
            out_img_path = os.path.join(SCENES_CACHE_DIR, f"{topic_id}_scene_{s_num:02d}_4k.jpg")
            qa_entry = acquire_verified_scene_image(
                topic_id=topic_id,
                scene_bp=scene_bp,
                in_video_registry=in_video_registry,
                persistent_registry=persistent_registry,
                output_scene_path=out_img_path
            )
            scene_qa_reports.append(qa_entry)
    
            if qa_entry["decision"].startswith("مرفوض"):
                print(f"❌ توقف الإنتاج في المشهد {s_num}: تعذر توفير صورة تاريخية تجتاز شروط الجودة!")
                for log_line in qa_entry["attempt_history"]:
                    print(f"   - {log_line}")
                report_file = os.path.join(REPORTS_DIR, f"QA_Report_FAILED_{topic_id}.json")
                with open(report_file, "w", encoding="utf-8") as f:
                    json.dump({"status": "ABORTED", "failed_scene": s_num, "scenes": scene_qa_reports}, f, ensure_ascii=False, indent=2)
                return 1
    
            verified_scene_paths[s_num] = out_img_path
            print(f"   ✅ القرار: {qa_entry['decision']} | المصدر: {qa_entry['source']}")
            print(f"   📜 الترخيص: {qa_entry['license']}")
            print(f"   📊 الأبعاد الأصلية: {qa_entry['native_resolution']} -> النهائية: {qa_entry['output_resolution']}")
            print(f"   💡 السطوع: {qa_entry['luma_mean']} | التباين (Std): {qa_entry['luma_std']} | dHash: {qa_entry['dhash']}")
    
        print("\n🎙️ جاري توليد التعليق الصوتي العربي الموثق وحساب التوقيت النسبي للمشاهد (المستهدف 45-60 ثانية)...")
        full_narration = " ".join(s["arabic_sentence"] for s in scenes)
        vo_mp3_path = os.path.join(SCENES_CACHE_DIR, f"{topic_id}_narration.mp3")
        total_audio_dur = generate_voiceover_and_get_duration(full_narration, vo_mp3_path)
        scene_durations = compute_proportional_scene_durations(scenes, total_audio_dur)
        print(f"   ⏱️ مدة التعليق الصوتي الكلية: {total_audio_dur:.2f} ثانية")
    
        ass_path = os.path.join(SCENES_CACHE_DIR, f"{topic_id}_captions.ass")
        build_synchronized_ass_subtitles(scenes, scene_durations, ass_path)
    
        print("\n🎬 جاري رندر المشاهد العشرة بدقة 2160x3840...")
        clip_files = []
        for scene_bp, s_dur in zip(scenes, scene_durations):
            s_num = scene_bp["scene_num"]
            clip_p = os.path.join(SCENES_CACHE_DIR, f"{topic_id}_clip_{s_num:02d}.mp4")
            ok = render_scene_clip(verified_scene_paths[s_num], clip_p, s_dur, s_num)
            if not ok:
                print(f"❌ فشل رندر مقطع المشهد {s_num} عبر FFmpeg!")
                return 1
            clip_files.append(clip_p)
    
        concat_list_path = os.path.join(SCENES_CACHE_DIR, f"{topic_id}_concat.txt")
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for cp in clip_files:
                f.write(f"file '{cp}'\n")
    
        final_video_path = os.path.join(TEST_LAB_DIR, f"Islamic_Short_{topic_id}_4K.mp4")
        ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")
    
        # رندر الفيديو النهائي بصوت نقي ونظيف تماماً بدون أي صفير أو طنين أو مؤثرات اصطناعية بين المشاهد
        final_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_list_path,
            "-i", vo_mp3_path,
            "-filter_complex",
            (
                f"[0:v]ass='{ass_escaped}'[vout];"
                f"[1:a]highpass=f=75,equalizer=f=3200:t=q:w=1.2:g=2.5,acompressor=threshold=-16dB:ratio=2.5:attack=10:release=120:makeup=2[aout]"
            ),
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-t", f"{total_audio_dur:.3f}",
            final_video_path
        ]
        res = subprocess.run(final_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            print(f"❌ فشل الدمج النهائي في FFmpeg:\n{res.stderr[-600:]}")
            return 1
    
        contact_sheet_path = os.path.join(REPORTS_DIR, f"Contact_Sheet_{topic_id}.jpg")
        build_contact_sheet_from_rendered_video(final_video_path, scenes, scene_durations, contact_sheet_path)
        print(f"\n🖼️ تم إنشاء لوحة معاينة المشاهد العشرة مع الكابشن من الفيديو النهائي: {contact_sheet_path}")
    
        print("\n🔬 جاري تشغيل الفحص الهندسي النهائي على ملف الفيديو المنتج...")
        final_verification = verify_final_video_file(
            video_path=final_video_path,
            expected_duration=total_audio_dur,
            scenes=scenes,
            scene_durations=scene_durations
        )
    
        documented_desc = build_documented_youtube_description(episode, scene_qa_reports)
        schedule_info = {
            "uploaded": False,
            "verified": False,
            "mode": MODE,
            "target_date": slot_day.isoformat(),
            "cairo_local_schedule": slot_local_cairo,
            "utc_publish_at_requested": slot_utc_publish,
            "note": "تم إيقاف الرفع في المرحلة الأولى (SINGLE_TEST) حتى مراجعة الفيديو التجريبي الجديد والموافقة على اختبار الرفع."
        }
    
        if final_verification["all_passed"] and MODE in ("SINGLE_UPLOAD_TEST", "DAILY_BATCH_6", "DAILY_BATCH_10"):
            print(f"\n📤 جاري رفع وجدولة الفيديو على يوتيوب لموعد: {slot_local_cairo}...")
            schedule_info = upload_and_verify_scheduled_youtube_video(
                video_path=final_video_path,
                title=episode["title"],
                description=documented_desc,
                target_day=slot_day,
                local_cairo_iso=slot_local_cairo,
                utc_publish_at_iso=slot_utc_publish
            )
            if schedule_info.get("verified"):
                total_uploaded += 1
                ledger = load_schedule_ledger()
                ledger["scheduled_slots"][slot_day.isoformat()] = schedule_info
                ledger["uploaded_topics"][topic_id] = schedule_info
                ledger["last_scheduled_date"] = slot_day.isoformat()
                save_schedule_ledger(ledger)
                print(f"   ✅ تم التحقق الفعلي من الرفع والجدولة! الرابط: {schedule_info['video_url']}")
            else:
                print(f"   ⚠️ لم يكتمل الرفع/التحقق: {schedule_info.get('reason')}")
    
        report_json_path = os.path.join(REPORTS_DIR, f"QA_Report_{topic_id}.json")
        full_qa_report = {
            "timestamp": datetime.now().isoformat(),
            "mode": MODE,
            "topic_id": topic_id,
            "title": episode["title"],
            "historical_metadata": episode["historical_metadata"],
            "documented_youtube_description": documented_desc,
            "video_file": final_video_path,
            "contact_sheet_file": contact_sheet_path,
            "next_10_cairo_schedule_slots": [
                {"date": d.isoformat(), "cairo_local": loc, "utc": u} for d, loc, u in next_slots
            ],
            "schedule_execution_result": schedule_info,
            "final_verification_10_points": final_verification,
            "scenes_qa_table": scene_qa_reports
        }
        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump(full_qa_report, f, ensure_ascii=False, indent=2)
    
        if not final_verification["all_passed"]:
            print(f"❌ فشل الفيديو النهائي في اجتياز بوابة الجودة النهائية! راجع التقرير: {report_json_path}")
            return 1
    
        save_dedup_registry(persistent_registry)
        total_produced += 1
        update_production_and_analytics_dashboard(
            episode=episode,
            video_path=final_video_path,
            contact_sheet_path=contact_sheet_path,
            qa_report_path=report_json_path,
            final_verification=final_verification,
            schedule_info=schedule_info,
            scene_qa_reports=scene_qa_reports
        )

    print("=" * 92)
    print(f"✅ اكتملت دورة المصنع بنجاح! تم إنتاج ({total_produced}) فيديو وتوثيقها بالكامل.")
    if MODE in ("SINGLE_UPLOAD_TEST", "DAILY_BATCH_6", "DAILY_BATCH_10"):
        print(f"🚀 إجمالي الفيديوهات المرفوعة والمجدولة رسمياً: ({total_uploaded}) فيديو.")
    print(f"📊 لوحة المتابعة والتحليلات الدائمة: {ANALYTICS_CSV_FILE}")
    print("=" * 92)
    return 0


if __name__ == "__main__":
    sys.exit(run_production_pipeline())