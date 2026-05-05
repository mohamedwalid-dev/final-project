# Khadamt – Team Git Workflow & Structure

## 📌 Tech Stack

* React
* Git & GitHub

---

## 🌳 Branching Strategy

* `main` → Stable / final version (protected)
* `dev` → Integration branch (protected)
* `feature/*` → Individual work branches

❌ No direct push to `main` or `dev`

---

## 🗂️ Project Structure

```
src/
 ├─ pages/
 │   ├─ auth/
 │   ├─ home/
 │   ├─ customerCare/
 │   ├─ hr/   
 │   ├─ dashboard/
 │   └─ finance/
 |   
 ├─ components/
 │   ├─ ui/
 │   ├─ layout/
 │   └─ common/
 │
 ├─ services/
 ├─ hooks/
 ├─ utils/
 ├─ styles/
 │
```

---

## 👥 Team Rules

* Each member works **only inside their assigned folder**
* Shared components go in `components/`
* API logic only in `services/`
* One feature = one branch = one PR
* Clear commit messages

---

## 🚀 First Time Setup (Copy–Paste)

```bash
git clone https://github.com/mohamedwalid-dev/Khadamt.git
cd Khadamt
git checkout dev
git pull origin dev
git checkout -b feature/your-feature-name
npm install
npm run dev
```

---

## ⬆️ Push Your Work

```bash
git add .
git commit -m "Add HR dashboard pages"
git push origin feature/your-feature-name
```

Then open **Pull Request** → `feature/*` → `dev`

---

## 📝 Commit Message Examples

✅ Good:

```
Add sales invoices page
Fix navbar responsive bug
```

❌ Bad:

```
update
fix
```

---

## ⚠️ Important Notes

* Do NOT change folder structure without approval
* Do NOT touch other teams' folders
* Resolve conflicts locally before PR

---

## ✅ Final Rule

> If it’s not reviewed, it doesn’t get merged.

Happy coding 🚀
