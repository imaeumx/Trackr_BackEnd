# TrackR - Watchlist Mobile App 🎬

A CRUD mobile application for managing movie watchlists, built with Django REST Framework backend and React Native (Expo) frontend.

## 📱 Project Overview

**TrackR** is a personal movie tracking app where users can:
- **Create** playlists (e.g., "Weekend Horror", "Must Watch Classics")
- **Read** their playlists and view movies inside them
- **Update** playlist names or movie watch status (To Watch → Watched)
- **Delete** playlists they no longer need

## 🛠 Tech Stack

### Backend
- **Framework:** Django 5.x + Django REST Framework
- **Database:** SQLite (development) / PostgreSQL (production)
- **Deployment:** Render.com
- **CORS:** django-cors-headers (for React Native access)

### Frontend
- **Platform:** React Native (Expo managed workflow)
- **Testing:** Snack.expo.dev
- **Navigation:** React Navigation
- **HTTP Client:** Axios

## 📁 Project Structure

```
CineStack/
├── CineStack/              # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── playlist/               # Main app
│   ├── models.py          # Movie, Playlist, PlaylistItem
│   ├── serializers.py     # DRF serializers
│   ├── views.py           # API ViewSets
│   ├── urls.py            # API routes
│   └── admin.py           # Admin configuration
├── manage.py
├── requirements.txt
├── build.sh               # Render deployment script
└── Procfile               # Gunicorn configuration
```

## 🚀 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/playlists/` | List all playlists |
| POST | `/api/playlists/` | Create a playlist |
| GET | `/api/playlists/{id}/` | Get playlist details |
| PUT | `/api/playlists/{id}/` | Update playlist |
| DELETE | `/api/playlists/{id}/` | Delete playlist |
| POST | `/api/playlists/{id}/add_movie/` | Add movie to playlist |
| DELETE | `/api/playlists/{id}/remove_movie/{movie_id}/` | Remove movie |
| PATCH | `/api/playlists/{id}/update_item_status/{movie_id}/` | Update status |
| GET | `/api/movies/` | List all movies |
| POST | `/api/movies/` | Create a movie |

## 🏃 Local Development

### 1. Clone and Setup
```bash
git clone https://github.com/imaeumx/Trackr_BackEnd
cd CineStack
```

### 2. Create Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Migrations
```bash
python manage.py migrate
```

### 5. Create Superuser (for Admin)
```bash
python manage.py createsuperuser
```

### 6. Run Development Server
```bash
python manage.py runserver
```

The API will be available at `http://127.0.0.1:8000/api/`

## 🧪 Running Tests
```bash
python manage.py test playlist
```

## 🌐 Deployment to Render.com

1. Push code to GitHub
2. Create a new **Web Service** on Render
3. Connect your GitHub repository
4. Configure:
   - **Build Command:** `./build.sh`
   - **Start Command:** `gunicorn CineStack.wsgi:application`
5. Add Environment Variables:
   - `SECRET_KEY` - Generate a secure key
   - `DEBUG` - Set to `False`
   - `ALLOWED_HOSTS` - Your Render URL
   - `DATABASE_URL` - PostgreSQL connection string (auto-added if using Render PostgreSQL)

## 👥 Team Workload Split

| Member | Role | Responsibilities |
|--------|------|------------------|
| **Patricia Alizah Henson** | Integration & Docs / Team Leader | Documentation, Wireframe Design, Frontend Screens, Backend, Axios API Calls, Testing |
| **Amaro Juno Alonzo** | Backend Lead | Django Setup, API Development, Database (Modeling/CRUD), Backend Services. |
| **Justin Vince Sunga** | Frontend Lead | React Native Screens, Backend, Navigation, UI/UX Styling, Deployment |

## 📝 License

This project is for educational purposes (C-PEITEL1 Final Project).
