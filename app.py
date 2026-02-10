from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
import os
from functools import wraps
import requests

# Création de l'application Flask
app = Flask(__name__)
CORS(app)  # Autorise les requêtes cross-origin

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'votre_clé_secrète_dev')

# Correction impérative pour PostgreSQL sur Render
database_url = os.environ.get('DATABASE_URL', 'sqlite:///labmath_db.sqlite')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Initialisation de la base de données
db = SQLAlchemy(app)

# Configuration pour l'API du site principal
SITE_URL = "https://labmath-scsmaubmar-org.onrender.com"
API_KEY = os.environ.get('API_KEY', 'votre_api_key')

# --- DÉCORATEUR SÉCURITÉ ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- MODÈLES ---
class Activite(db.Model):
    __tablename__ = 'activites'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    contenu = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    auteur = db.Column(db.String(100))
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    date_modification = db.Column(db.DateTime, onupdate=datetime.utcnow)
    est_publie = db.Column(db.Boolean, default=True)

class Realisation(db.Model):
    __tablename__ = 'realisations'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    categorie = db.Column(db.String(100))
    date_realisation = db.Column(db.Date)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

class Annonce(db.Model):
    __tablename__ = 'annonces'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    contenu = db.Column(db.Text)
    type_annonce = db.Column(db.String(50))
    date_debut = db.Column(db.DateTime)
    date_fin = db.Column(db.DateTime)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    est_active = db.Column(db.Boolean, default=True)

class Offre(db.Model):
    __tablename__ = 'offres'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    type_offre = db.Column(db.String(50))
    lieu = db.Column(db.String(100))
    date_limite = db.Column(db.Date)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    est_active = db.Column(db.Boolean, default=True)

# --- ROUTES AUTHENTIFICATION ---

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin_user = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_pass = os.environ.get('ADMIN_PASSWORD', 'admin123')
        
        if username == admin_user and password == admin_pass:
            session['user_id'] = 1
            session['username'] = username
            flash('Connexion réussie!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Identifiants incorrects', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Vous avez été déconnecté', 'info')
    return redirect(url_for('login'))

# --- ROUTES DASHBOARD ---

@app.route('/dashboard')
@login_required
def dashboard():
    stats = {
        'activities_count': Activite.query.count(),
        'realisations_count': Realisation.query.count(),
        'annonces_count': Annonce.query.count(),
        'offres_count': Offre.query.count(),
        'activities_published': Activite.query.filter_by(est_publie=True).count(),
        'annonces_active': Annonce.query.filter_by(est_active=True).count(),
        'offres_active': Offre.query.filter_by(est_active=True).count()
    }
    
    # Dernières activités
    recent_activities = Activite.query.order_by(Activite.date_creation.desc()).limit(5).all()
    recent_annonces = Annonce.query.order_by(Annonce.date_creation.desc()).limit(5).all()
    recent_offres = Offre.query.order_by(Offre.date_creation.desc()).limit(5).all()
    
    return render_template('dashboard.html', 
                          stats=stats, 
                          now=datetime.utcnow(),
                          recent_activities=recent_activities,
                          recent_annonces=recent_annonces,
                          recent_offres=recent_offres)

# --- ROUTES ACTIVITÉS ---

@app.route('/activites')
@login_required
def activites():
    activites_list = Activite.query.order_by(Activite.date_creation.desc()).all()
    return render_template('activites.html', activites=activites_list)

@app.route('/activite/nouveau', methods=['GET', 'POST'])
@login_required
def nouvel_activite():
    if request.method == 'POST':
        try:
            # Gérer le champ est_publie
            est_publie = request.form.get('est_publie') == 'true'
            
            nouvelle = Activite(
                titre=request.form.get('titre'),
                description=request.form.get('description'),
                contenu=request.form.get('contenu'),
                image_url=request.form.get('image_url'),
                auteur=session.get('username', 'Admin'),
                est_publie=est_publie
            )
            db.session.add(nouvelle)
            db.session.commit()
            flash('Activité créée avec succès!', 'success')
            return redirect(url_for('activites'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la création: {str(e)}', 'danger')
            return render_template('edit_activite.html', action='nouveau', activite=None)
    
    return render_template('edit_activite.html', action='nouveau', activite=None)

@app.route('/activite/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_activite(id):
    activite = Activite.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            activite.titre = request.form.get('titre')
            activite.description = request.form.get('description')
            activite.contenu = request.form.get('contenu')
            activite.image_url = request.form.get('image_url')
            activite.est_publie = request.form.get('est_publie') == 'true'
            activite.date_modification = datetime.utcnow()
            
            db.session.commit()
            flash('Activité mise à jour avec succès!', 'success')
            return redirect(url_for('activites'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la mise à jour: {str(e)}', 'danger')
    
    return render_template('edit_activite.html', action='modifier', activite=activite)

@app.route('/activite/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_activite(id):
    activite = Activite.query.get_or_404(id)
    try:
        db.session.delete(activite)
        db.session.commit()
        flash('Activité supprimée avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la suppression: {str(e)}', 'danger')
    
    return redirect(url_for('activites'))

@app.route('/activite/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_activite(id):
    activite = Activite.query.get_or_404(id)
    try:
        activite.est_publie = not activite.est_publie
        db.session.commit()
        status = "publiée" if activite.est_publie else "dépubliée"
        flash(f'Activité {status} avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'danger')
    
    return redirect(url_for('activites'))

# --- ROUTES RÉALISATIONS ---

@app.route('/realisations')
@login_required
def realisations():
    realisations_list = Realisation.query.order_by(Realisation.date_creation.desc()).all()
    return render_template('realisations.html', realisations=realisations_list)

@app.route('/realisation/nouveau', methods=['GET', 'POST'])
@login_required
def nouvelle_realisation():
    if request.method == 'POST':
        try:
            date_realisation = None
            if request.form.get('date_realisation'):
                date_realisation = datetime.strptime(request.form.get('date_realisation'), '%Y-%m-%d').date()
            
            nouvelle = Realisation(
                titre=request.form.get('titre'),
                description=request.form.get('description'),
                image_url=request.form.get('image_url'),
                categorie=request.form.get('categorie'),
                date_realisation=date_realisation
            )
            db.session.add(nouvelle)
            db.session.commit()
            flash('Réalisation créée avec succès!', 'success')
            return redirect(url_for('realisations'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la création: {str(e)}', 'danger')
    
    return render_template('edit_realisation.html', action='nouveau', realisation=None)

@app.route('/realisation/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_realisation(id):
    realisation = Realisation.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            realisation.titre = request.form.get('titre')
            realisation.description = request.form.get('description')
            realisation.image_url = request.form.get('image_url')
            realisation.categorie = request.form.get('categorie')
            
            if request.form.get('date_realisation'):
                realisation.date_realisation = datetime.strptime(request.form.get('date_realisation'), '%Y-%m-%d').date()
            else:
                realisation.date_realisation = None
            
            db.session.commit()
            flash('Réalisation mise à jour avec succès!', 'success')
            return redirect(url_for('realisations'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la mise à jour: {str(e)}', 'danger')
    
    return render_template('edit_realisation.html', action='modifier', realisation=realisation)

@app.route('/realisation/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_realisation(id):
    realisation = Realisation.query.get_or_404(id)
    try:
        db.session.delete(realisation)
        db.session.commit()
        flash('Réalisation supprimée avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la suppression: {str(e)}', 'danger')
    
    return redirect(url_for('realisations'))

# --- ROUTES ANNONCES ---

@app.route('/annonces')
@login_required
def annonces():
    annonces_list = Annonce.query.order_by(Annonce.date_creation.desc()).all()
    return render_template('annonces.html', annonces=annonces_list)

@app.route('/annonce/nouveau', methods=['GET', 'POST'])
@login_required
def nouvelle_annonce():
    if request.method == 'POST':
        try:
            date_debut = None
            date_fin = None
            
            if request.form.get('date_debut'):
                date_debut = datetime.strptime(request.form.get('date_debut'), '%Y-%m-%dT%H:%M')
            if request.form.get('date_fin'):
                date_fin = datetime.strptime(request.form.get('date_fin'), '%Y-%m-%dT%H:%M')
            
            est_active = request.form.get('est_active') == 'true'
            
            nouvelle = Annonce(
                titre=request.form.get('titre'),
                contenu=request.form.get('contenu'),
                type_annonce=request.form.get('type_annonce'),
                date_debut=date_debut,
                date_fin=date_fin,
                est_active=est_active
            )
            db.session.add(nouvelle)
            db.session.commit()
            flash('Annonce créée avec succès!', 'success')
            return redirect(url_for('annonces'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la création: {str(e)}', 'danger')
    
    return render_template('edit_annonce.html', action='nouveau', annonce=None)

@app.route('/annonce/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_annonce(id):
    annonce = Annonce.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            annonce.titre = request.form.get('titre')
            annonce.contenu = request.form.get('contenu')
            annonce.type_annonce = request.form.get('type_annonce')
            annonce.est_active = request.form.get('est_active') == 'true'
            
            if request.form.get('date_debut'):
                annonce.date_debut = datetime.strptime(request.form.get('date_debut'), '%Y-%m-%dT%H:%M')
            else:
                annonce.date_debut = None
            
            if request.form.get('date_fin'):
                annonce.date_fin = datetime.strptime(request.form.get('date_fin'), '%Y-%m-%dT%H:%M')
            else:
                annonce.date_fin = None
            
            db.session.commit()
            flash('Annonce mise à jour avec succès!', 'success')
            return redirect(url_for('annonces'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la mise à jour: {str(e)}', 'danger')
    
    return render_template('edit_annonce.html', action='modifier', annonce=annonce)

@app.route('/annonce/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_annonce(id):
    annonce = Annonce.query.get_or_404(id)
    try:
        db.session.delete(annonce)
        db.session.commit()
        flash('Annonce supprimée avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la suppression: {str(e)}', 'danger')
    
    return redirect(url_for('annonces'))

@app.route('/annonce/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_annonce(id):
    annonce = Annonce.query.get_or_404(id)
    try:
        annonce.est_active = not annonce.est_active
        db.session.commit()
        status = "activée" if annonce.est_active else "désactivée"
        flash(f'Annonce {status} avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'danger')
    
    return redirect(url_for('annonces'))

# --- ROUTES OFFRES ---

@app.route('/offres')
@login_required
def offres():
    offres_list = Offre.query.order_by(Offre.date_creation.desc()).all()
    return render_template('offres.html', offres=offres_list)

@app.route('/offre/nouveau', methods=['GET', 'POST'])
@login_required
def nouvelle_offre():
    if request.method == 'POST':
        try:
            date_limite = None
            if request.form.get('date_limite'):
                date_limite = datetime.strptime(request.form.get('date_limite'), '%Y-%m-%d').date()
            
            est_active = request.form.get('est_active') == 'true'
            
            nouvelle = Offre(
                titre=request.form.get('titre'),
                description=request.form.get('description'),
                type_offre=request.form.get('type_offre'),
                lieu=request.form.get('lieu'),
                date_limite=date_limite,
                est_active=est_active
            )
            db.session.add(nouvelle)
            db.session.commit()
            flash('Offre créée avec succès!', 'success')
            return redirect(url_for('offres'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la création: {str(e)}', 'danger')
    
    return render_template('edit_offre.html', action='nouveau', offre=None)

@app.route('/offre/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_offre(id):
    offre = Offre.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            offre.titre = request.form.get('titre')
            offre.description = request.form.get('description')
            offre.type_offre = request.form.get('type_offre')
            offre.lieu = request.form.get('lieu')
            offre.est_active = request.form.get('est_active') == 'true'
            
            if request.form.get('date_limite'):
                offre.date_limite = datetime.strptime(request.form.get('date_limite'), '%Y-%m-%d').date()
            else:
                offre.date_limite = None
            
            db.session.commit()
            flash('Offre mise à jour avec succès!', 'success')
            return redirect(url_for('offres'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la mise à jour: {str(e)}', 'danger')
    
    return render_template('edit_offre.html', action='modifier', offre=offre)

@app.route('/offre/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_offre(id):
    offre = Offre.query.get_or_404(id)
    try:
        db.session.delete(offre)
        db.session.commit()
        flash('Offre supprimée avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la suppression: {str(e)}', 'danger')
    
    return redirect(url_for('offres'))

@app.route('/offre/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_offre(id):
    offre = Offre.query.get_or_404(id)
    try:
        offre.est_active = not offre.est_active
        db.session.commit()
        status = "activée" if offre.est_active else "désactivée"
        flash(f'Offre {status} avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'danger')
    
    return redirect(url_for('offres'))

# --- ROUTES API POUR SYNCHRONISATION ---

@app.route('/api/sync/activite/<int:id>', methods=['POST'])
@login_required
def sync_activite(id):
    """Synchronise une activité avec le site principal"""
    activite = Activite.query.get_or_404(id)
    
    try:
        headers = {
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'titre': activite.titre,
            'description': activite.description,
            'contenu': activite.contenu,
            'image_url': activite.image_url,
            'auteur': activite.auteur,
            'date_creation': activite.date_creation.isoformat() if activite.date_creation else None,
            'est_publie': activite.est_publie
        }
        
        # Appel à l'API du site principal
        response = requests.post(
            f'{SITE_URL}/api/activites',
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            return jsonify({'success': True, 'message': 'Activité synchronisée'})
        else:
            return jsonify({'success': False, 'message': f'Erreur API: {response.status_code}'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# --- GESTION DES ERREURS ---

@app.errorhandler(404)
def page_not_found(e):
    if 'user_id' in session:
        return render_template('404.html'), 404
    return redirect(url_for('login'))

@app.errorhandler(500)
def internal_server_error(e):
    if 'user_id' in session:
        return render_template('500.html', error=str(e)), 500
    return redirect(url_for('login'))

# --- INITIALISATION ---
with app.app_context():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    db.create_all()
    
    # Créer un compte admin par défaut si aucun utilisateur n'existe
    # (Ceci est juste pour la démo, en production utilisez les variables d'environnement)
    pass

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)