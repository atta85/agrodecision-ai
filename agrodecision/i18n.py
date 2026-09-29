"""Interface text in English, Urdu, Punjabi (Shahmukhi), Sindhi and Roman Urdu.

IMPORTANT: these labels are a first draft. Please have native speakers review them
(especially Punjabi and Sindhi) before farmers use the app. Missing keys fall back to English.
Add or fix translations only in this file.
"""
from __future__ import annotations

LANGS = ["en", "ur", "pa", "sd", "ur_roman"]
LANG_LABELS = {"en": "English", "ur": "اردو", "pa": "پنجابی", "sd": "سنڌي", "ur_roman": "Roman Urdu"}
RTL = {"ur", "pa", "sd"}


def _t(en, ur, pa, sd, rom):
    return {"en": en, "ur": ur, "pa": pa, "sd": sd, "ur_roman": rom}


T = {
    "tagline": _t("Helps you decide what to do about a crop problem. You always make the final decision.",
                  "فصل کے مسئلے پر فیصلہ کرنے میں مدد۔ حتمی فیصلہ ہمیشہ آپ کا ہے۔",
                  "فصل دے مسئلے بارے فیصلہ کرن وچ مدد۔ آخری فیصلہ ہمیشہ تہاڈا اے۔",
                  "فصل جي مسئلي تي فيصلو ڪرڻ ۾ مدد. آخري فيصلو هميشه توهان جو آهي.",
                  "Fasal ke masle par faisla karne mein madad. Aakhri faisla hamesha aap ka hai."),
    "step1": _t("1. Tell us about the problem", "۱۔ مسئلے کے بارے میں بتائیں", "۱۔ مسئلے بارے دسو",
                "1. مسئلي بابت ٻڌايو", "1. Masle ke baare mein batayein"),
    "region": _t("Where is the field?", "کھیت کہاں ہے؟", "کھیت کتھے اے؟", "پوکي ڪٿي آهي؟", "Khet kahan hai?"),
    "country": _t("Country", "ملک", "ملک", "ملڪ", "Mulk"),
    "province": _t("Province / state", "صوبہ", "صوبہ", "صوبو", "Soba"),
    "city": _t("City / town / village", "شہر / قصبہ / گاؤں", "شہر / قصبہ / پنڈ", "شهر / ڳوٺ", "Shehar / qasba / gaon"),
    "find_place": _t("Find my place", "میری جگہ تلاش کریں", "میری تھاں لبھو", "منهنجي جاءِ ڳوليو", "Meri jagah talash karein"),
    "pick_place": _t("Choose the correct place", "درست جگہ منتخب کریں", "ٹھیک تھاں چنو", "صحيح جاءِ چونڊيو", "Durust jagah chunein"),
    "no_place": _t("Place not found. Type coordinates below, or continue without location.",
                   "جگہ نہیں ملی۔ نیچے کوآرڈینیٹس لکھیں یا مقام کے بغیر آگے بڑھیں۔",
                   "تھاں نہیں لبھی۔ تھلے کوآرڈینیٹس لکھو یا بغیر تھاں دے اگے ودھو۔",
                   "جاءِ نه ملي. هيٺ ڪوآرڊينيٽس لکو يا جاءِ کانسواءِ اڳتي وڌو.",
                   "Jagah nahin mili. Neeche coordinates likhein ya location ke baghair aage barhein."),
    "crop": _t("Crop", "فصل", "فصل", "فصل", "Fasal"),
    "crop_other": _t("Other crop (type the name)", "دوسری فصل (نام لکھیں)", "ہور فصل (ناں لکھو)", "ٻي فصل (نالو لکو)", "Doosri fasal (naam likhein)"),
    "stage": _t("Growth stage", "نشوونما کا مرحلہ", "ودھن دا مرحلہ", "واڌ جو مرحلو", "Nashonuma ka marhala"),
    "area": _t("Field area", "کھیت کا رقبہ", "کھیت دا رقبہ", "پوکي جو رقبو", "Khet ka raqba"),
    "area_unit": _t("Unit", "اکائی", "اکائی", "يونٽ", "Ikai"),
    "symptoms": _t("What do you see? (select all that apply)", "آپ کو کیا نظر آتا ہے؟ (جو لاگو ہو منتخب کریں)",
                   "تہانوں کی دِسدا اے؟ (جیہڑے لاگو ہون چنو)", "توهان کي ڇا نظر اچي ٿو؟ (جيڪي لاڳو ٿين چونڊيو)",
                   "Aap ko kya nazar aata hai? (jo lagu ho chunein)"),
    "affected": _t("How many plants look affected?", "کتنے پودے متاثر لگتے ہیں؟", "کنے بوٹے متاثر لگدے نیں؟",
                   "ڪيترا ٻوٽا متاثر لڳن ٿا؟", "Kitne paude mutasir lagte hain?"),
    "onset": _t("When did it start?", "یہ کب شروع ہوا؟", "ایہہ کدوں شروع ہویا؟", "اهو ڪڏهن شروع ٿيو؟", "Yeh kab shuru hua?"),
    "spread": _t("Is it spreading?", "کیا یہ پھیل رہا ہے؟", "کیہ ایہہ پھیل رہیا اے؟", "ڇا اهو پکڙجي رهيو آهي؟", "Kya yeh phail raha hai?"),
    "irrigation": _t("How is the field watered?", "کھیت کو پانی کیسے دیا جاتا ہے؟", "کھیت نوں پانی کِداں دِتا جاندا اے؟",
                     "پوکي کي پاڻي ڪيئن ڏنو وڃي ٿو؟", "Khet ko pani kaise diya jata hai?"),
    "soil": _t("Soil type (if you know)", "مٹی کی قسم (اگر معلوم ہو)", "مٹی دی قسم (جے پتا ہووے)",
               "مٽيءَ جو قسم (جي خبر هجي)", "Mitti ki qisam (agar maloom ho)"),
    "describe": _t("Describe the problem in your own words", "مسئلہ اپنے الفاظ میں بیان کریں", "مسئلہ اپنے لفظاں وچ دسو",
                   "مسئلو پنهنجن لفظن ۾ بيان ڪريو", "Masla apne alfaaz mein bayan karein"),
    "describe_help": _t("Write in your own language. Mention recent changes (weather, water, fertiliser, spray).",
                        "اپنی زبان میں لکھیں۔ حالیہ تبدیلیاں بتائیں (موسم، پانی، کھاد، سپرے)۔",
                        "اپنی زبان وچ لکھو۔ حالیہ تبدیلیاں دسو (موسم، پانی، کھاد، سپرے)۔",
                        "پنهنجي ٻولي ۾ لکو. تازيون تبديليون ٻڌايو (موسم، پاڻي، ڀاڻ، اسپري).",
                        "Apni zabaan mein likhein. Haal ki tabdiliyan batayein (mausam, pani, khaad, spray)."),
    "photos_hdr": _t("Photos (optional, up to 3)", "تصاویر (اختیاری، زیادہ سے زیادہ 3)", "تصویراں (اختیاری، ودھ توں ودھ 3)",
                     "تصويرون (اختياري، وڌ ۾ وڌ 3)", "Tasveerein (ikhtiyari, ziyada se ziyada 3)"),
    "photos_help": _t("JPG, PNG or PDF, up to 10 MB each. Show the whole plant, a close-up of a leaf (top and underside), and the soil.",
                      "JPG, PNG یا PDF، ہر ایک 10 MB تک۔ پورا پودا، پتے کا قریبی منظر (اوپر اور نیچے) اور مٹی دکھائیں۔",
                      "JPG, PNG یا PDF، ہر اک 10 MB تک۔ پورا بوٹا، پتے دی نیڑیوں تصویر (اُتے تے تھلے) تے مٹی وکھاؤ۔",
                      "JPG, PNG يا PDF، هر هڪ 10 MB تائين. پورو ٻوٽو، پن جي ويجهي تصوير (مٿي ۽ هيٺ) ۽ مٽي ڏيکاريو.",
                      "JPG, PNG ya PDF, har ek 10 MB tak. Poora paudha, patte ka qareebi manzar (upar aur neeche) aur mitti dikhayein."),
    "camera": _t("Take a photo with your camera (optional)", "کیمرے سے تصویر لیں (اختیاری)", "کیمرے نال تصویر کھِچو (اختیاری)",
                 "ڪئميرا سان تصوير وٺو (اختياري)", "Camera se tasveer lein (ikhtiyari)"),
    "docs_hdr": _t("Your own documents (optional)", "آپ کی اپنی دستاویزات (اختیاری)", "تہاڈے اپنے کاغذات (اختیاری)",
                   "توهان جا پنهنجا دستاويز (اختياري)", "Aap ke apne dastaavez (ikhtiyari)"),
    "sop": _t("Rules / SOP file (PDF or TXT)", "اصول / SOP فائل (PDF یا TXT)", "اصول / SOP فائل (PDF یا TXT)",
              "اصول / SOP فائل (PDF يا TXT)", "Usool / SOP file (PDF ya TXT)"),
    "prices": _t("Price list (CSV)", "قیمتوں کی فہرست (CSV)", "قیمتاں دی لسٹ (CSV)", "قيمتن جي فهرست (CSV)", "Qeematon ki fehrist (CSV)"),
    "inventory": _t("Stock / inventory (CSV)", "ذخیرہ / انوینٹری (CSV)", "ذخیرہ / انوینٹری (CSV)", "ذخيرو / انوينٽري (CSV)", "Zakheera / inventory (CSV)"),
    "money_hdr": _t("Money (recommended)", "رقم (تجویز کردہ)", "رقم (تجویز کیتی)", "رقم (تجويز ڪيل)", "Raqam (tajweez kardah)"),
    "currency": _t("Currency", "کرنسی", "کرنسی", "ڪرنسي", "Currency"),
    "value_at_risk": _t("Estimated value of the crop at risk", "خطرے میں فصل کی تخمینی قیمت", "خطرے وچ فصل دی اندازاً قیمت",
                        "خطري ۾ فصل جي اندازي مطابق قيمت", "Khatre mein fasal ki taqreebi qeemat"),
    "measure_hdr": _t("Measurements (only if you have them)", "پیمائشیں (صرف اگر آپ کے پاس ہوں)", "ماپ (صرف جے تہاڈے کول ہون)",
                      "ماپ (رڳو جيڪڏهن توهان وٽ هجن)", "Paimaishein (sirf agar aap ke paas hon)"),
    "ec": _t("Soil/water EC (dS/m)", "مٹی/پانی EC (dS/m)", "مٹی/پانی EC (dS/m)", "مٽي/پاڻي EC (dS/m)", "Mitti/pani EC (dS/m)"),
    "ph": _t("pH", "pH", "pH", "pH", "pH"),
    "temp": _t("Temperature (°C)", "درجہ حرارت (°C)", "درجہ حرارت (°C)", "گرمي پد (°C)", "Darja hararat (°C)"),
    "continue": _t("Continue", "آگے بڑھیں", "اگے ودھو", "اڳتي وڌو", "Aage barhein"),
    "confirm_hdr": _t("Please check that we understood you", "براہ کرم تصدیق کریں کہ ہم نے آپ کو صحیح سمجھا",
                      "مہربانی کرکے تصدیق کرو کہ اسیں تہانوں ٹھیک سمجھیا", "مهرباني ڪري تصديق ڪريو ته اسان توهان کي صحيح سمجهيو",
                      "Meherbani karke tasdeeq karein ke hum ne aap ko sahi samjha"),
    "we_understood": _t("What we understood:", "ہم نے یہ سمجھا:", "اسیں ایہہ سمجھیا:", "اسان هي سمجهيو:", "Hum ne yeh samjha:"),
    "english_used": _t("English version used by the system:", "سسٹم میں استعمال ہونے والا انگریزی متن:",
                       "سسٹم وچ ورتیا جان والا انگریزی متن:", "سسٽم ۾ استعمال ٿيندڙ انگريزي متن:",
                       "System mein istemal hone wala angrezi matan:"),
    "yes_run": _t("Yes, correct - start analysis", "جی ہاں، درست ہے - تجزیہ شروع کریں", "ہاں، ٹھیک اے - تجزیہ شروع کرو",
                  "ها، صحيح آهي - تجزيو شروع ڪريو", "Ji haan, durust hai - tajziya shuru karein"),
    "no_edit": _t("No - go back and edit", "نہیں - واپس جا کر ترمیم کریں", "نہیں - پِچھے جا کے تبدیل کرو",
                  "نه - واپس وڃي ترميم ڪريو", "Nahin - wapas ja kar tabdeel karein"),
    "running": _t("Analysing... this can take a few minutes on the free plan.", "تجزیہ جاری ہے... مفت پلان پر چند منٹ لگ سکتے ہیں۔",
                  "تجزیہ چل رہیا اے... مفت پلان تے کجھ منٹ لگ سکدے نیں۔", "تجزيو جاري آهي... مفت پلان تي ڪجهه منٽ لڳي سگهن ٿا.",
                  "Tajziya jaari hai... muft plan par chand minute lag sakte hain."),
    "summary_hdr": _t("Summary", "خلاصہ", "خلاصہ", "خلاصو", "Khulasa"),
    "cause_hdr": _t("Most likely cause (NOT confirmed)", "سب سے ممکنہ وجہ (تصدیق شدہ نہیں)", "سبھ توں ممکنہ وجہ (تصدیق نہیں ہوئی)",
                    "سڀ کان ممڪن سبب (تصديق ٿيل ناهي)", "Sab se mumkin wajah (tasdeeq shuda nahin)"),
    "options_hdr": _t("Your options", "آپ کے اختیارات", "تہاڈے اختیار", "توهان جا اختيار", "Aap ke ikhtiyarat"),
    "next_steps": _t("Next steps", "اگلے اقدامات", "اگلے قدم", "اڳيان جا قدم", "Agle iqdamaat"),
    "warnings": _t("Warnings", "انتباہ", "خبردار", "خبردار", "Intibah"),
    "decision_hdr": _t("Your decision", "آپ کا فیصلہ", "تہاڈا فیصلہ", "توهان جو فيصلو", "Aap ka faisla"),
    "approve": _t("APPROVE", "منظور", "منظور", "منظور", "MANZOOR"),
    "modify": _t("MODIFY", "تبدیل", "تبدیل", "تبديل", "TABDEEL"),
    "reject": _t("REJECT", "مسترد", "رد", "رد", "RADD"),
    "more_info": _t("MORE INFORMATION", "مزید معلومات", "ہور معلومات", "وڌيڪ معلومات", "MAZEED MALOOMAT"),
    "choose_option": _t("Choose an option", "ایک اختیار منتخب کریں", "اک اختیار چنو", "هڪ اختيار چونڊيو", "Ek ikhtiyar chunein"),
    "reason": _t("Reason (optional)", "وجہ (اختیاری)", "وجہ (اختیاری)", "سبب (اختياري)", "Wajah (ikhtiyari)"),
    "save_decision": _t("Save decision", "فیصلہ محفوظ کریں", "فیصلہ محفوظ کرو", "فيصلو محفوظ ڪريو", "Faisla mehfooz karein"),
    "saved": _t("Decision saved.", "فیصلہ محفوظ ہو گیا۔", "فیصلہ محفوظ ہو گیا۔", "فيصلو محفوظ ٿي ويو.", "Faisla mehfooz ho gaya."),
    "new_case": _t("New case", "نیا کیس", "نواں کیس", "نئون ڪيس", "Naya case"),
    "history": _t("History", "تاریخ", "تاریخ", "تاريخ", "Tareekh"),
    "disclaimer": _t("This tool supports decisions. It does not replace an agronomist. Check any chemical use with an expert and local rules.",
                     "یہ ٹول فیصلے میں مدد دیتا ہے، ماہرِ زراعت کا متبادل نہیں۔ کسی بھی کیمیکل کے استعمال سے پہلے ماہر اور مقامی قوانین سے تصدیق کریں۔",
                     "ایہہ ٹول فیصلے وچ مدد دیندا اے، ماہرِ زراعت دا متبادل نہیں۔ کسے وی کیمیکل توں پہلاں ماہر تے مقامی قانون توں تصدیق کرو۔",
                     "هي اوزار فيصلي ۾ مدد ڏئي ٿو، زرعي ماهر جو متبادل ناهي. ڪنهن به ڪيميڪل کان اڳ ماهر ۽ مقامي قانونن کان تصديق ڪريو.",
                     "Yeh tool faisle mein madad deta hai, mahir-e-zaraat ka mutabadil nahin. Kisi bhi chemical ke istemal se pehle mahir aur maqami qawaneen se tasdeeq karein."),
    "access_code": _t("Access code", "رسائی کوڈ", "رسائی کوڈ", "رسائي ڪوڊ", "Access code"),
}

_UNK = _t("Not sure", "معلوم نہیں", "پتا نہیں", "خبر ناهي", "Maloom nahin")

# option groups: key -> labels. The ENGLISH label is what the agents receive.
OPT = {
    "crop": {
        "wheat": _t("Wheat", "گندم", "کنک", "ڪڻڪ", "Gandum"),
        "rice": _t("Rice", "چاول", "چاول", "چانور", "Chawal"),
        "cotton": _t("Cotton", "کپاس", "کپاس", "ڪپهه", "Kapas"),
        "sugarcane": _t("Sugarcane", "گنا", "گنا", "ڪمند", "Ganna"),
        "maize": _t("Maize", "مکئی", "مکئی", "مڪئي", "Makai"),
        "citrus": _t("Citrus (kinnow / orange)", "کینو / مالٹا", "کِنّو / مالٹا", "ڪينو / مالٽو", "Kinnow / Malta"),
        "mango": _t("Mango", "آم", "انب", "انب", "Aam"),
        "potato": _t("Potato", "آلو", "آلو", "بطاٽا", "Aloo"),
        "tomato": _t("Tomato", "ٹماٹر", "ٹماٹر", "ٽماٽو", "Tamatar"),
        "onion": _t("Onion", "پیاز", "پیاز", "ڪانڍو", "Pyaz"),
        "chili": _t("Chili", "مرچ", "مرچ", "مرچ", "Mirch"),
        "other": _t("Other", "دیگر", "ہور", "ٻيو", "Doosri"),
    },
    "stage": {
        "seedling": _t("Seedling", "ابتدائی پودا", "ابتدائی بوٹا", "شروعاتي ٻوٽو", "Ibtidai paudha"),
        "vegetative": _t("Vegetative growth", "بڑھوتری", "ودھن", "واڌ", "Barhotri"),
        "flowering": _t("Flowering", "پھول آنا", "پھُل آؤنا", "گل ڦلڻ", "Phool aana"),
        "fruiting": _t("Fruit / grain formation", "پھل / دانے بننا", "پھل / دانے بنّنا", "ميوو / داڻا ٺهڻ", "Phal / daane banna"),
        "harvest": _t("Near harvest", "کٹائی کے قریب", "کٹائی دے نیڑے", "لڻڻ جي ويجهو", "Katai ke qareeb"),
        "unknown": _UNK,
    },
    "symptoms": {
        "yellowing": _t("Yellowing leaves", "پتوں کا پیلا ہونا", "پتیاں دا پیلا ہونا", "پنن جو پيلو ٿيڻ", "Patton ka peela hona"),
        "spots": _t("Spots on leaves or fruit", "پتوں یا پھل پر دھبے", "پتیاں یا پھل تے دھبے", "پنن يا ميوي تي داغ", "Patton ya phal par dhabbe"),
        "wilting": _t("Wilting / drooping", "مرجھانا / جھکنا", "مرجھاؤنا / جھکنا", "سڪڻ / ڍرو ٿيڻ", "Murjhana / jhukna"),
        "stunted": _t("Slow or stunted growth", "سست یا رکی ہوئی نشوونما", "سست یا رُکی ہوئی ودھ", "سست يا رڪيل واڌ", "Sust ya ruki hui nashonuma"),
        "curling": _t("Leaf curling", "پتوں کا مڑنا", "پتیاں دا مڑنا", "پنن جو ورڻ", "Patton ka murna"),
        "fruit_drop": _t("Flowers or fruit dropping", "پھول یا پھل گرنا", "پھُل یا پھل ڈگنا", "گل يا ميوو ڪرڻ", "Phool ya phal girna"),
        "root_brown": _t("Brown or rotting roots", "جڑوں کا بھورا ہونا یا گلنا", "جڑاں دا بھورا ہونا یا گلنا", "پاڙن جو ناسي ٿيڻ يا سڙڻ", "Jadon ka bhoora hona ya galna"),
        "white_powder": _t("White powder or mould", "سفید پاؤڈر یا پھپھوندی", "چٹا پاؤڈر یا پھپھوندی", "اڇو پائوڊر يا ڦھڪو", "Safed powder ya phaphoondi"),
        "insects": _t("Insects or webbing visible", "کیڑے یا جالے نظر آنا", "کیڑے یا جالے دِسنا", "ڪيڙا يا جالا نظر اچڻ", "Keeray ya jaalay nazar aana"),
        "leaf_burn": _t("Dry, burnt leaf edges", "پتوں کے کنارے سوکھے/جلے ہوئے", "پتیاں دے کنارے سکے/سڑے ہوئے", "پنن جا ڪنارا سڪل/ٻرل", "Patton ke kinare sukhe/jale hue"),
        "holes": _t("Holes or chewed leaves", "پتوں میں سوراخ یا کترے ہوئے", "پتیاں وچ سوراخ یا کُترے ہوئے", "پنن ۾ ڇيد يا ڪتريل", "Patton mein suraakh ya katre hue"),
    },
    "affected": {
        "lt10": _t("Less than 10%", "10٪ سے کم", "10٪ توں گھٹ", "10٪ کان گهٽ", "10% se kam"),
        "10_25": _t("10 to 25%", "10 سے 25٪", "10 توں 25٪", "10 کان 25٪", "10 se 25%"),
        "25_50": _t("25 to 50%", "25 سے 50٪", "25 توں 50٪", "25 کان 50٪", "25 se 50%"),
        "gt50": _t("More than 50%", "50٪ سے زیادہ", "50٪ توں ودھ", "50٪ کان وڌيڪ", "50% se ziyada"),
        "unknown": _UNK,
    },
    "onset": {
        "days": _t("In the last few days", "پچھلے چند دنوں میں", "پچھلے کجھ دناں وچ", "گذريل ڪجهه ڏينهن ۾", "Pichhle chand dinon mein"),
        "weeks": _t("1 to 4 weeks ago", "1 سے 4 ہفتے پہلے", "1 توں 4 ہفتے پہلاں", "1 کان 4 هفتا اڳ", "1 se 4 hafte pehle"),
        "longer": _t("More than a month ago", "ایک مہینے سے زیادہ پہلے", "اک مہینے توں ودھ پہلاں", "هڪ مهيني کان وڌيڪ اڳ", "Ek mahine se ziyada pehle"),
        "unknown": _UNK,
    },
    "spread": {
        "fast": _t("Yes, quickly", "جی ہاں، تیزی سے", "ہاں، تیزی نال", "ها، تيزيءَ سان", "Ji haan, tezi se"),
        "slow": _t("Yes, slowly", "جی ہاں، آہستہ", "ہاں، ہولی", "ها، آهستي", "Ji haan, aahista"),
        "no": _t("No", "نہیں", "نہیں", "نه", "Nahin"),
        "unknown": _UNK,
    },
    "irrigation": {
        "canal": _t("Canal water", "نہری پانی", "نہری پانی", "واهه جو پاڻي", "Nehri pani"),
        "tubewell": _t("Tubewell / pump", "ٹیوب ویل / پمپ", "ٹیوب ویل / پمپ", "ٽيوب ويل / پمپ", "Tubewell / pump"),
        "drip": _t("Drip / sprinkler", "ڈرپ / سپرنکلر", "ڈرپ / سپرنکلر", "ڊرپ / اسپرنڪلر", "Drip / sprinkler"),
        "rain": _t("Rain only", "صرف بارش", "صرف مینہ", "رڳو برسات", "Sirf barish"),
        "unknown": _UNK,
    },
    "soil": {
        "sandy": _t("Sandy (light)", "ریتلی (ہلکی)", "ریتلی (ہولی)", "واريءَ وارو (هلڪو)", "Retli (halki)"),
        "loam": _t("Loam (medium)", "درمیانی (میرا)", "درمیانی (میرا)", "ميرو (وچولو)", "Darmiyani (maira)"),
        "clay": _t("Clay (heavy)", "چکنی (بھاری)", "چکنی (بھاری)", "چڪڻي (ڳرو)", "Chikni (bhaari)"),
        "salty": _t("White salt crust / kallar patches", "سفید نمک / کلر کے دھبے", "چٹے لون / کلر دے دھبے", "اڇي لوڻ / ڪلر جا داغ", "Safed namak / kallar ke dhabbe"),
        "unknown": _UNK,
    },
}

AREA_UNITS = ["acre", "hectare", "kanal", "marla"]
CURRENCIES = ["PKR", "USD", "INR", "EUR", "GBP", "SAR", "AED"]


def t(key: str, lang: str) -> str:
    d = T.get(key)
    if not d:
        return key
    return d.get(lang) or d["en"]


def opt_label(group: str, key: str, lang: str) -> str:
    d = OPT[group].get(key)
    if not d:
        return key
    return d.get(lang) or d["en"]


def opt_en(group: str, key: str) -> str:
    return OPT[group][key]["en"]


def opt_keys(group: str) -> list[str]:
    return list(OPT[group].keys())
