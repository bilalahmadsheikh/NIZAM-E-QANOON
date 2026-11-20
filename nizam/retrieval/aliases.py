"""The legal alias index (D-105; docs/04 R0 "Roman Urdu is first-class"): Urdu-script and Roman Urdu legal terms ->
the English words the statute book uses, added to the lexical query so BM25 can match a question it otherwise cannot
read. A Roman Urdu question ("Talaq ke baad shohar ko kis ko notice dena zaroori hai?") shares almost no words with
the English text of the law; an Urdu-script question shares none.

    gloss("Na-qabil-e-zamanat jurm mein zamanat kab mil sakti hai?") -> ['non-bailable', 'offence', 'bail', ...]

Rules:
  * it applies only to a question written in Urdu -- Urdu script, or Roman Urdu recognised by its function words
    (hai, mein, kya, ka, ki, ke ...); an English question is never changed;
  * general legal vocabulary across family, property, criminal, labour, money, procedure and public law -- written
    from the statute book's own terms, not from any golden question;
  * Roman Urdu matching is on whole words, after folding common spelling variants (k/q, doubled letters, aa/a,
    ee/i, oo/u, a trailing h): 'tallaq', 'talak' and 'talaaq' meet 'talaq';
  * Urdu-script matching is on the exact word, diacritics and the zero-width non-joiner removed;
  * multi-word terms ('haq mehr', 'makan malik', 'nan nafqa') are matched before their parts;
  * the gloss only ADDS words: the question's own words stay in the lexical query.
The table is data; growing it toward docs/04's 400-600 concepts is curation, measured on dev each time.
"""
from __future__ import annotations

import re
import unicodedata

# English gloss  <-  Roman Urdu forms, comma-separated  |  Urdu-script forms, comma-separated
_TABLE = """
divorce talaq                    <- talaq, talak, tilaq                      | طلاق
khula dissolution marriage       <- khula                                     | خلع
marriage nikah                   <- nikah, shadi, biyah                       | نکاح, شادی
nikahnama marriage contract      <- nikahnama, nikah-nama, nikah nama         | نکاح نامہ, نکاحنامہ
dower                            <- mehr, mahr, haq mehr, haq-mehr, haqmehr   | مہر, حق مہر
maintenance                      <- nafqa, nafaqa, nan nafqa, kharcha         | نفقہ, نان نفقہ, خرچہ
husband                          <- shohar, shauhar, khawind                  | شوہر, خاوند
wife                             <- biwi, bivi, zauja                         | بیوی, زوجہ
second marriage polygamy         <- dusri shadi                               | دوسری شادی
guardian guardianship            <- wali, sarparast                           | ولی, سرپرست
custody guardianship minor       <- tahwil, hizanat                           | تحویل, حضانت
child children minor             <- bacha, bache, bachon, bachay, bachi        | بچہ, بچے, بچوں, بچی
child marriage                   <- kam umri ki shadi                         | کم عمری کی شادی
inheritance succession           <- wirasat, virasat, wirsa, warasat, tarka   | وراثت, ورثہ, ترکہ
heir heirs                       <- waris, warisan                            | وارث, ورثاء
share                            <- hissa                                     | حصہ
daughter sister women            <- beti, behan, aurat, khawatin              | بیٹی, بہن, عورت, خواتین
property                         <- jaidad, jaedad, milkiyat                  | جائیداد, ملکیت
land                             <- zamin                                     | زمین
guarantor surety                 <- ka zamin, ki zamin, ke zamin, zamin bana, zamin hun | ضامن
possession dispossession         <- kabza, najaiz kabza                       | قبضہ, ناجائز قبضہ
girl female minor                <- larki, larkiyan                           | لڑکی, لڑکیوں
boy male minor                   <- larka, larke                              | لڑکا, لڑکے
age years                        <- umar, umr, sal                            | عمر, سال
ten years                        <- das sal                                   | دس سال
twelve years                     <- barah sal, bara sal                       | بارہ سال
fourteen years                   <- chaudah sal, chauda sal                   | چودہ سال
fifteen years                    <- pandrah sal, pandra sal                   | پندرہ سال
sixteen years                    <- solah sal, sola sal                       | سولہ سال
seventeen years                  <- satrah sal, satra sal                     | سترہ سال
eighteen years                   <- athara sal, atharah sal                   | اٹھارہ سال
exit control                     <- ecl, exit control list                    | ای سی ایل
grounds reasons                  <- wajah, wajuhat                            | وجہ, وجوہات
lawful                           <- jaiz                                      | جائز
unlawful illegal                 <- najaiz, na-jaiz                           | ناجائز, غیر قانونی
badla-e-sulh wanni swara         <- swara, vani, wani, wanni                  | سوارہ, ونی
jirga panchayat                  <- jirga, panchayat                          | جرگہ, پنچایت
birth                            <- paidaish, paidaesh                        | پیدائش
magistrate                       <- majistret                                 | مجسٹریٹ
produced before                  <- pesh                                      | پیش
deprived depriving               <- mehrum                                    | محروم
electronic information system    <- online, internet, social media, facebook  | آن لائن, انٹرنیٹ, سوشل میڈیا
dishonour                        <- bauns, bounce                             | باؤنس
ban prohibition                  <- pabandi, mumaniat                         | پابندی, ممانعت
liable liability responsible     <- zimedar, zimedari                         | ذمہ دار, ذمہ داری
reputation defamation            <- izat, badnami, izat kharab                | عزت, بدنامی
false                            <- jhuti, jhoti                              | جھوٹی, جھوٹا
permission consent               <- ijazat, razamandi                         | اجازت, رضامندی
decision order judgment          <- faisla, faisle                            | فیصلہ, فیصلے
compensation damages             <- muawza, harjana                           | معاوضہ, ہرجانہ
loss damage                      <- nuksan                                    | نقصان
right                            <- hak                                       | حق
lawful legal                     <- kanuni                                    | قانونی
law                              <- kanun                                     | قانون
missing                          <- lapata                                    | لاپتہ
appeal                           <- apil                                      | اپیل
case suit                        <- mukadma                                   | مقدمہ, کیس
voter electoral roll             <- voter list                                | ووٹر, ووٹر لسٹ
rent controller                  <- rent kantrolar                            | رینٹ کنٹرولر, رینٹ
court                            <- kort                                      | کورٹ
police                           <- polis                                     | پولیس
days limitation                  <- din                                       | دن
period                           <- muddat                                    | مدت
house premises                   <- ghar, makan                               | گھر, مکان
plot                             <- plat                                      | پلاٹ
rent tenant tenancy              <- kiraya, kirayedar, kirayadar              | کرایہ, کرایہ دار
landlord                         <- makan malik                               | مالک مکان
eviction                         <- bedakhli, be-dakhli                       | بے دخلی
sale                             <- farokht, bechna                           | فروخت
purchase buyer                   <- kharid, kharidar                          | خرید, خریدار
registration registered          <- registri, indraj                          | رجسٹری, اندراج
agreement contract               <- muahida, iqrarnama, iqrar nama            | معاہدہ, اقرارنامہ
gift                             <- hiba, tohfa                               | ہبہ, تحفہ
mortgage                         <- girvi, rehan                              | گروی, رہن
record of rights                 <- fard, jamabandi                           | فرد, جمع بندی
mutation                         <- intikal, intekal                          | انتقال
pre-emption                      <- shufa, haq shufa                          | شفعہ
neighbour                        <- hamsaya, hamsaye, padosi                  | ہمسایہ, پڑوسی
way easement                     <- rasta                                     | راستہ
bail                             <- zamanat                                   | ضمانت
non-bailable offence             <- na-kabil-e-zamanat, nakabil-e-zamanat     | ناقابل ضمانت
arrest                           <- giraftar, giraftari, pakra, pakar         | گرفتار, گرفتاری
first information report         <- parcha                                    | پرچہ
police station                   <- thana                                     | تھانہ
court                            <- adalat, kachehri                          | عدالت, کچہری
lawyer advocate                  <- wakil, vakil                              | وکیل
complaint application            <- shikayat, darkhwast                       | شکایت, درخواست
punishment sentence              <- saza                                      | سزا
offence crime                    <- jurm, jurum                               | جرم
murder qatl                      <- katl                                      | قتل
theft                            <- chori                                     | چوری
robbery dacoity                  <- dakaiti                                   | ڈکیتی
cheating fraud                   <- dhoka, dhokha, dhoke, dhokhe              | دھوکہ, دھوکے, دھوکا, دھوکہ دہی
forgery forged                   <- jali, jalsazi                             | جعلی, جعلسازی
signature                        <- dastakhat, dastkhat                       | دستخط
threat intimidation              <- dhamki                                    | دھمکی
hurt injury                      <- zakhm, zakhmi, chot                       | زخم, چوٹ
harassment                       <- hirasani                                  | ہراسانی
kidnapping abduction             <- aghwa                                     | اغوا
confession                       <- ikbal-e-jurm, ikbal e jurm                | اقبال جرم, اقبالِ جرم
evidence witness                 <- sabut, gawah, gawahi                      | ثبوت, گواہ, گواہی
custody remand                   <- hirasat                                   | حراست, ریمانڈ
imprisonment jail                <- kaid                                      | قید, جیل
fine                             <- jurmana                                   | جرمانہ
narcotics drugs                  <- manshiyat, charas, bhang                  | منشیات, چرس, بھنگ
domestic violence                <- gharelu tashadud                          | گھریلو تشدد
violence assault                 <- tashadud, mar pit                         | تشدد
dowry                            <- jahez, jahaiz                             | جہیز
loan debt                        <- karz, karza                               | قرض
interest                         <- sud                                       | سود
guarantor surety                 <- zamin dar                                 | ضامن
cheque                          <- chaik, chek                               | چیک
salary wages                     <- tankhwa, tankha, ujrat                    | تنخواہ, اجرت
employment worker                <- naukri, mulazmat, mulazim, mazdur         | ملازمت, ملازم, مزدور, نوکری
minimum wage                     <- kam az kam ujrat                          | کم از کم اجرت
factory                          <- karkhana                                  | کارخانہ
maternity                        <- zachgi                                    | زچگی
leave                            <- chuti                                     | چھٹی
tax                              <- mehsul                                    | ٹیکس, محصول
income tax return                <- income tax return                         | انکم ٹیکس, ریٹرن
identity card NADRA              <- shanakhti card                            | شناختی کارڈ, نادرا
vote election                    <- intikhab, intikhabat                      | ووٹ, انتخابات, انتخاب
right rights                     <- huquq                                     | حق, حقوق
constitution                     <- ain, dastur                               | آئین, دستور
government                       <- hukumat, sarkar                           | حکومت, سرکار
consumer                         <- sarif, sarifin                            | صارف
shop                             <- dukan                                     | دکان
insurance                        <- bima                                      | بیمہ
partnership partner              <- shirakat, sharik                          | شراکت, شریک
disability                       <- mazuri, mazur                             | معذوری, معذور
environment pollution            <- mahol, aludgi                             | ماحول, آلودگی
negligence                       <- laparwahi                                 | لاپرواہی
hospital                         <- haspatal                                  | ہسپتال
education                        <- talim                                     | تعلیم
protest assembly                 <- ehtijaj                                   | احتجاج
"""

# words that mark a Latin-script question as Roman Urdu (none is an English word a legal question would use)
_ROMAN_MARKERS = frozenset("""hai hain mein mujhe mera meri mere hum humara kya kia ka ki ke ko se ne kar karna karein
karoon karun kaise kahan kab kitne kitna nahi nahin aur ya agar lekin bhi tak wala wali wale sakta sakti sakte hoon
hun raha rahi rahe diya diye gaya gayi tha thi apna apni apne unka unki iska uski koi kuch""".split())


# Roman Urdu function words beyond the markers: the frame of a Roman Urdu sentence, as query.FRAME is of an English
# one. They match nothing in the English statute book, so in the lexical query they only dilute its content words
# (D-109); the markers and these are dropped from a Roman Urdu question's lexical query, never from its text.
_ROMAN_FRAME = _ROMAN_MARKERS | frozenset("""yeh ye woh wo us is un in jo jab tab phir sirf bas abhi ab pehle baad
liye lie wala wali wale par pe per ka ki ke ko ki kis kisi kaun kon kyun kyon kyunke kaisa kaisi hota hoti hote hua
hui hue karta karti karte kiya kiye kartay de dena deta deti dete le lena leta leti mil milta milti milna sak saka
saki chahiye chahye zaroori zaruri hona hoga hogi honge tou to ji sahab""".split())


def roman_frame(word: str) -> bool:
    return word.lower() in _ROMAN_FRAME


def _fold(word: str) -> str:
    w = word.lower().replace("q", "k")
    w = re.sub(r"aa+", "a", w)
    w = re.sub(r"ee+", "i", w)
    w = re.sub(r"oo+", "u", w)
    w = re.sub(r"(.)\1+", r"\1", w)
    return w[:-1] if len(w) > 3 and w.endswith("h") else w


def _clean_ur(word: str) -> str:
    """diacritics, the zero-width non-joiner and Urdu punctuation (، ؛ ؟ ۔) removed"""
    w = unicodedata.normalize("NFC", word).replace("‌", "")
    return "".join(ch for ch in w if not unicodedata.category(ch).startswith("M") and ch not in "،؛؟۔")


def _build():
    latin: dict[tuple[str, ...], str] = {}
    urdu: dict[tuple[str, ...], str] = {}
    for line in _TABLE.strip().splitlines():
        gloss_words, _, rest = line.partition("<-")
        roman, _, ur = rest.partition("|")
        g = " ".join(gloss_words.split())
        for form in (f.strip() for f in roman.split(",")):
            if form:
                latin.setdefault(tuple(_fold(p) for p in form.split()), g)
        for form in (f.strip() for f in ur.split(",")):
            if form:
                urdu.setdefault(tuple(_clean_ur(p) for p in form.split()), g)
    return latin, urdu


_LATIN, _URDU = _build()
_MAXLEN = max(len(k) for k in list(_LATIN) + list(_URDU))
_WORD = re.compile(r"[A-Za-z][A-Za-z-]*|[؀-ۿ‌]+")


def is_urdu(text: str) -> bool:
    """Urdu script, or Roman Urdu: at least two of its function words"""
    if re.search(r"[؀-ۿ]", text or ""):
        return True
    words = re.findall(r"[a-z]+", (text or "").lower())
    return sum(1 for w in words if w in _ROMAN_MARKERS) >= 2


def gloss(text: str) -> list[str]:
    """English words for the legal terms an Urdu-language question uses (longest phrase first), in order, no repeats;
    [] for an English question"""
    if not is_urdu(text):
        return []
    toks = _WORD.findall(text or "")
    keys = [(_fold(t), "l") if t[0].isascii() else (_clean_ur(t), "u") for t in toks]
    out: list[str] = []
    i = 0
    while i < len(keys):
        for n in range(min(_MAXLEN, len(keys) - i), 0, -1):
            span = keys[i:i + n]
            if len({kind for _, kind in span}) != 1:
                continue
            table = _LATIN if span[0][1] == "l" else _URDU
            g = table.get(tuple(w for w, _ in span))
            if g:
                for w in g.split():
                    if w not in out:
                        out.append(w)
                i += n
                break
        else:
            i += 1
    return out
