# HAMU_GPT WEB — poora website version

Yeh **bilkul wahi app** hai jo `C:\Users\Amanat 777\Desktop\HAMU-GPT\dist\HAMU-GPT.exe`
me hai — sirf browser ke liye. Wahi `index.html`, wahi backend, wahi saare features.

Fark sirf yeh hai ke yeh Chrome me chalta hai aur Vercel pe deploy ho sakta hai.

---

## 0. Sabse aasan tareeqa — `start.bat`

**`start.bat` pe double-click karo. Bas.** Yeh sab khud karta hai:

1. Python khud dhoondta hai (agar na mile to saaf bata deta hai)
2. Check karta hai ke saari files mojood hain (koi missing ho to naam batata hai)
3. Free port dhoondta hai — 8000 busy ho to khud 8001, 8002... chun leta hai
4. Server start karta hai
5. **Browser khud khol deta hai**

Band karne ke liye: us window me **Ctrl+C**, ya window close kar do.

> Agar Python na ho to `start.bat` khud bata dega aur install ka link de dega.

---

## 0b. Poora order — kis tarteeb se karna hai

```
1. start.bat double-click        → local pe test (sirf tumhara PC)
2. GitHub pe upload
3. Vercel pe deploy              → live URL milega (https://...vercel.app)
4. Woh URL Adsterra me add karo  → approval 5-10 minute me
5. Ad code paste karo            → <template id="adHeadCode"> ke andar
6. GitHub pe dobara commit       → Vercel khud redeploy karega
7. Live site pe check karo
```

⚠️ **Adsterra ko live HTTPS URL chahiye.** `start.bat` jo chalata hai woh
`http://127.0.0.1:8000` hai — **sirf tumhara PC**. Adsterra woh accept nahi karega,
aur internet pe koi aur bhi nahi dekh sakta. `start.bat` sirf **local testing** ke
liye hai.

⚠️ **Adsterra "under construction" ya khaali site reject kar deta hai** (Clause 4.2).
Site live hone ke baad hi apply karo, aur Privacy Policy ka link kaam karta ho.

✅ **Privacy Policy aur cookie consent pehle se lag chuke hain.** Adsterra inhein
lazmi maangta hai (Clause 4.9):
- `ui/privacy.html` — `/privacy` aur `/privacy.html` dono pe khulti hai
- Cookie bar — Accept / Decline. Decline karne pe ad code **load hi nahi hota**
- Sidebar me neeche **Cookie settings** aur **Privacy** ke link

---

## 0c. Accounts permanent rakhne ke liye — Upstash Redis (lazmi!)

**Yeh step chhorna mat.** Iske bagair accounts **har restart pe mit jayenge**.

Wajah: Vercel ka filesystem **read-only** hai. Account save karne ki sirf ek jagah
hoti hai — `/tmp` — aur woh **har cold start pe saaf ho jati hai**. Yani user signup
kare, aur thodi der baad uska account gayab.

Isi liye app ab **Upstash Redis** (key-value store) me likhta hai jab woh hosted ho.
Desktop app waise hi apne PC pe files me likhta rehta hai — wahan koi farq nahi.

### Lagane ka tareeqa (2 minute, free)

```
1. Vercel dashboard → apna project kholo
2. Upar "Storage" tab → "Create Database"
3. "Upstash" → "Redis" chuno
4. Naam do (jaise hamu-gpt) → region apne paas wala → Create
5. "Connect Project" → apna project select karo → Connect
6. Project → Deployments → "Redeploy" dabao (zaroori hai!)
```

Vercel khud do environment variables laga deta hai:

```
KV_REST_API_URL
KV_REST_API_TOKEN
```

App inhe khud padh leta hai. **Koi code change nahi, koi package install nahi** —
Upstash ka REST API plain `urllib` se chalta hai, is liye `requirements.txt` khaali
rehta hai.

### Sach hai ke chal gaya?

Deploy ke baad:

1. Site pe ek account banao
2. Vercel me dobara **Redeploy** karo (yani zabardasti restart)
3. Wapas login karo — **account aur chats hone chahiye**

Agar mit gaye to matlab Upstash connect nahi hua. Vercel → Settings →
Environment Variables me dekh lo ke `KV_REST_API_URL` mojood hai.

> `python nexus_app.py --selftest` bhi yeh bata deta hai — "accounts at:" line
> dekho. Agar wahan "files (no key-value store configured)" likha ho aur hosted
> chal raha ho, to warning bhi aayegi.

---

## 1. Files — sab upload karni hain

| File | Kaam |
|---|---|
| **`start.bat`** | **double-click — sab kuch khud chal jata hai** |
| `ui/index.html` | **poora interface** — wahi file jo app me hai |
| `ui/logo.png` | HAMU logo (zaroori — warna logo toota dikhega) |
| `ui/logo-small.png` | chhota logo |
| `nexus_app.py` | poora backend |
| `auth.py` | accounts, password hashing |
| `store.py` | per-account storage |
| `ads.py` | ad-for-time system |
| `providers.py` | AI providers, models |
| `tools.py` | agent tools |
| `verify.py` | model identity check |
| `wsgi.py` | **Vercel ka entry point** |
| `vercel.json` | Vercel config |
| `requirements.txt` | dependencies (khaali — sab built-in) |
| `.gitignore` | kachra upload na ho |

⚠️ **`index.html` akela kaafi NAHI.** Woh sirf dikhne wala hissa hai. Agar sirf HTML
khola jaye to chat shell dikhega magar niche "starting…" atka rahega aur kuch kaam
nahi karega — kyunki accounts, providers aur chat sab Python backend se aate hain.

⚠️ **`ui/logo.png` bhoolna nahi.** Woh `index.html` ke saath relative path se aata hai.

---

## 2. GitHub pe daalo

1. github.com → **New repository** → naam `hamu-gpt-web` → **Create**
2. **uploading an existing file** pe click karo
3. Is folder ki **saari** files drag karo — `ui` folder bhi (uske andar
   `index.html`, `logo.png`, `logo-small.png` hain)
4. **Commit changes**

Git se karna ho:

```
git init
git add .
git commit -m "HAMU_GPT WEB"
git branch -M main
git remote add origin https://github.com/TUMHARA-USERNAME/hamu-gpt-web.git
git push -u origin main
```

---

## 3. Vercel pe deploy

1. vercel.com → **Add New** → **Project** → repo import karo
2. **Framework Preset:** `Other`
3. **Build Command / Output Directory / Install Command:** teenon **khaali** chhoro
4. **Deploy**

`vercel.json` pehle se set hai — Vercel khud `wsgi.py` uthayega.

Link milega jaise `https://hamu-gpt-web.vercel.app`. Apna domain: **Settings →
Domains**.

---

## 4. Local pe test karna (deploy se pehle)

**Sabse aasan:** `start.bat` pe double-click.

Ya haath se:

```
python wsgi.py
```

Phir browser me kholo: **http://127.0.0.1:8000**

Yahi cheez Vercel pe chalegi — pehle yahan check kar lo.

---

## 5. Adsterra code lagana

⚠️ **Pehle `ui/index.html` me `<head>` wala comment dhoondo. Ab wahan khaali comment
nahi, ek `<template id="adHeadCode">` hai. Adsterra ka code USKE ANDAR paste karna hai,
comment ke andar nahi.**

```html
<!-- >>> PASTE ADSTERRA HEAD CODE BELOW >>> -->
<template id="adHeadCode">

     <<<<<< YAHAN PASTE KARO — bas yahi ek jagah >>>>>>

</template>
<!-- <<< PASTE ADSTERRA HEAD CODE ABOVE <<< -->
```

**Template kyun?** Browser template ke andar ki cheezein **chalata nahi**. Code sirf
tab page me jata hai jab visitor cookies accept kare. Decline kare to woh **kabhi load
hi nahi hota**. Yeh Adsterra ki shart hai (cookies consent), aur "Decline" ka matlab
bhi sach me kuch hona chahiye.

Seedha comment ke bahar paste karne se ads **sab ko** dikhne lagte — bina pooche.

**Banner bhi lagana ho** to `#siteAdSlot` ke andar daal do. Khaali rehne tak woh slot
dikhta hi nahi, layout bilkul waisa rehta hai.

⚠️ **Comment ke andar kabhi asli script tag mat likhna** — browser use asli samajh
leta hai aur poori page ka JavaScript kharab ho jata hai. (`_ui_integrity_test.js`
isi galti ko pakadta hai.)

### Kaunse formats lagane hain

| Format | Kamai | Layout pe asar |
|---|---|---|
| **Social Bar** | sabse zyada | **koi nahi** — jagah nahi chahiye |
| **Popunder** | zyada | **koi nahi** — jagah nahi chahiye |
| In-Page Push | achhi | halka — content ke saath fit ho jata hai |
| Banner 300×250 | kam | sidebar slot tayyar hai |

Naye site ke liye **Social Bar + Popunder** sabse behtar hai — dono ko page pe jagah
nahi chahiye, is liye interface bilkul waisa hi rehta hai jaisa hai.

⚠️ **"Ad dekho → time lo" web pe kabhi nahi.** Adsterra ki Publisher Terms, Clause 6
bullet (iv): publishers *"shall not... use incentives to increase volumes of
impressions, clicks or actions."* Todne pe **account terminate + jama shuda paisa
zabt** (Clause 7.5). Web pe chat free rehta hai, paisa normal display ads se aata hai.

---

## 6. Jo cheezein web pe alag hain — aur kyun

Zyaadatar sab kuch bilkul same hai. Yeh 4 cheezein jaan-boojh kar alag hain:

| Cheez | App me | Web pe | Kyun |
|---|---|---|---|
| **Ad dekho → time lo** | chalta hai | **band** | Yeh incentivized traffic hai — Adsterra/HilltopAds mana karte hain. Web pe chat free hai, paisa normal display ads se aayega |
| **Agent mode** | chalta hai | **band** | App me machine tumhari hai. Web pe woh **server** hai — koi bhi visitor command chala sakta tha. Web pe toggle dabane se ek sheet khulti hai: *"Download desktop app to access Agent mode"* + Download button |
| **Continue with Google** | chalta hai | **chalta hai** (local pe) | Woh jis machine pe backend chal raha hai uska Chrome padhta hai. Local `--web` pe wahi tumhara PC hai — to chalta hai. Asli host (Vercel) pe Chrome nahi hota, is liye button khud chhup jata hai |
| **File browser / preview** | chalta hai | band | Woh server ki files dikhata |

Baqi sab — chat, providers, models, verify, chats history, attachments, themes,
admin panel — **bilkul same** hain.

---

## 7. Do zaroori baatein

**(a) Vercel pe data tikta nahi.** Vercel ka filesystem read-only hai, is liye app
`/tmp` me likhta hai. Naya deploy ya cold start pe accounts aur chats **mit sakte
hain**. Asli users ke liye database chahiye — Vercel Postgres / Supabase / Turso.

**(b) Public link pe koi bhi sign-up kar sakta hai.** Per-account isolation users ko
ek doosre se alag rakhta hai, duniya se nahi.

---

## 8. Kuch toot jaye to

| Dikkat | Wajah |
|---|---|
| Chat shell dikhe, "starting…" atka ho | Backend nahi chal raha — `python wsgi.py` chalao |
| Logo toota hua | `ui/logo.png` upload nahi hua |
| Har API call pe 404 | `vercel.json` upload nahi hua |
| "Backend not connected" | Wahi — backend nahi mila |
