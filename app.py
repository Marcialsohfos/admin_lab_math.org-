from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from functools import wraps
import jwt
import requests

# Création de l'application Flask EN PREMIER
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'votre_clé_secrète_dev')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://user:password@localhost/labmath_db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Initialisation de la base de données
db = SQLAlchemy(app)

# Configuration pour l'API du site principal
SITE_URL = "https://labmath-scsmaubmar-org.onrender.com"
API_KEY = os.environ.get('API_KEY', 'votre_api_key')

# Décorateur pour les routes protégées
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Définition des modèles
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
    
    def to_dict(self):
        return {
            'id': self.id,
            'titre': self.titre,
            'description': self.description,
            'contenu': self.contenu,
            'image_url': self.image_url,
            'auteur': self.auteur,
            'date_creation': self.date_creation.isoformat() if self.date_creation else None,
            'est_publie': self.est_publie
        }

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

# MAINTENANT, définissez vos routes APRÈS la création de 'app'

# Routes principales
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
    
    return render_template('login.html', hide_sidebar=True)

@app.route('/logout')
def logout():
    session.clear()
    flash('Déconnexion réussie', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    stats = {
        'activities_count': Activite.query.count(),
        'realisations_count': Realisation.query.count(),
        'annonces_count': Annonce.query.count(),
        'offres_count': Offre.query.count()
    }
    return render_template('dashboard.html', stats=stats, now=datetime.utcnow())

# Routes pour les activités
@app.route('/activites')
@login_required
def activites():
    activites_list = Activite.query.order_by(Activite.date_creation.desc()).all()
    return render_template('activites.html', activites=activites_list, now=datetime.utcnow())

@app.route('/activite/nouveau', methods=['GET', 'POST'])
@login_required
def nouvel_activite():
    if request.method == 'POST':
        titre = request.form.get('titre')
        description = request.form.get('description')
        contenu = request.form.get('contenu')
        image_url = request.form.get('image_url')
        
        nouvelle_activite = Activite(
            titre=titre,
            description=description,
            contenu=contenu,
            image_url=image_url,
            auteur=session.get('username', 'Admin'),
            date_creation=datetime.utcnow()
        )
        
        try:
            db.session.add(nouvelle_activite)
            db.session.commit()
            
            # Synchroniser avec le site principal
            sync_activite(nouvelle_activite)
            
            flash('Activité créée avec succès!', 'success')
            return redirect(url_for('activites'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'danger')
    
    return render_template('edit_activite.html', action='nouveau', activite=None)

@app.route('/activite/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_activite(id):
    activite = Activite.query.get_or_404(id)
    
    if request.method == 'POST':
        activite.titre = request.form.get('titre')
        activite.description = request.form.get('description')
        activite.contenu = request.form.get('contenu')
        activite.image_url = request.form.get('image_url')
        activite.date_modification = datetime.utcnow()
        
        try:
            db.session.commit()
            sync_activite(activite)
            flash('Activité modifiée avec succès!', 'success')
            return redirect(url_for('activites'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'danger')
    
    return render_template('edit_activite.html', activite=activite, action='modifier')

@app.route('/activite/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_activite(id):
    activite = Activite.query.get_or_404(id)
    
    try:
        db.session.delete(activite)
        db.session.commit()
        
        # Synchroniser la suppression avec le site principal
        sync_delete('activite', id)
        
        flash('Activité supprimée avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'danger')
    
    return redirect(url_for('activites'))

# Routes pour les réalisations
@app.route('/realisations')
@login_required
def realisations():
    realisations_list = Realisation.query.order_by(Realisation.date_creation.desc()).all()
    stats = {
        'realisations_count': Realisation.query.count(),
        'realisations_with_images': Realisation.query.filter(Realisation.image_url != None).count()
    }
    return render_template('realisations.html', realisations=realisations_list, stats=stats, now=datetime.utcnow())

@app.route('/realisation/nouvelle', methods=['GET', 'POST'])
@login_required
def nouvelle_realisation():
    if request.method == 'POST':
        titre = request.form.get('titre')
        description = request.form.get('description')
        categorie = request.form.get('categorie')
        image_url = request.form.get('image_url')
        date_realisation_str = request.form.get('date_realisation')
        
        date_realisation = None
        if date_realisation_str:
            date_realisation = datetime.strptime(date_realisation_str, '%Y-%m-%d').date()
        
        nouvelle_realisation = Realisation(
            titre=titre,
            description=description,
            categorie=categorie,
            image_url=image_url,
            date_realisation=date_realisation,
            date_creation=datetime.utcnow()
        )
        
        try:
            db.session.add(nouvelle_realisation)
            db.session.commit()
            
            sync_realisation(nouvelle_realisation)
            
            flash('Réalisation créée avec succès!', 'success')
            return redirect(url_for('realisations'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'danger')
    
    stats = {
        'realisations_count': Realisation.query.count(),
        'realisations_with_images': Realisation.query.filter(Realisation.image_url != None).count()
    }
    return render_template('edit_realisation.html', realisation=None, stats=stats)

@app.route('/realisation/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_realisation(id):
    realisation = Realisation.query.get_or_404(id)
    
    if request.method == 'POST':
        realisation.titre = request.form.get('titre')
        realisation.description = request.form.get('description')
        realisation.categorie = request.form.get('categorie')
        realisation.image_url = request.form.get('image_url')
        
        date_realisation_str = request.form.get('date_realisation')
        if date_realisation_str:
            realisation.date_realisation = datetime.strptime(date_realisation_str, '%Y-%m-%d').date()
        else:
            realisation.date_realisation = None
        
        try:
            db.session.commit()
            sync_realisation(realisation)
            flash('Réalisation modifiée avec succès!', 'success')
            return redirect(url_for('realisations'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'danger')
    
    stats = {
        'realisations_count': Realisation.query.count(),
        'realisations_with_images': Realisation.query.filter(Realisation.image_url != None).count()
    }
    return render_template('edit_realisation.html', realisation=realisation, stats=stats)

@app.route('/realisation/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_realisation(id):
    realisation = Realisation.query.get_or_404(id)
    
    try:
        db.session.delete(realisation)
        db.session.commit()
        sync_delete('realisation', id)
        flash('Réalisation supprimée avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'danger')
    
    return redirect(url_for('realisations'))

# Routes pour les annonces
@app.route('/annonces')
@login_required
def annonces():
    annonces_list = Annonce.query.order_by(Annonce.date_creation.desc()).all()
    return render_template('annonces.html', annonces=annonces_list, now=datetime.utcnow())

@app.route('/annonce/nouvelle', methods=['GET', 'POST'])
@app.route('/annonce/nouvelle/<string:type>', methods=['GET', 'POST'])
@login_required
def nouvelle_annonce(type='info'):
    annonce = None
    if request.method == 'POST':
        titre = request.form.get('titre')
        type_annonce = request.form.get('type_annonce')
        contenu = request.form.get('contenu')
        date_debut_str = request.form.get('date_debut')
        date_fin_str = request.form.get('date_fin')
        est_active = request.form.get('est_active') == 'true'
        
        date_debut = None
        date_fin = None
        
        if date_debut_str:
            date_debut = datetime.strptime(date_debut_str, '%Y-%m-%dT%H:%M')
        if date_fin_str:
            date_fin = datetime.strptime(date_fin_str, '%Y-%m-%dT%H:%M')
        
        nouvelle_annonce = Annonce(
            titre=titre,
            type_annonce=type_annonce,
            contenu=contenu,
            date_debut=date_debut,
            date_fin=date_fin,
            est_active=est_active,
            date_creation=datetime.utcnow()
        )
        
        try:
            db.session.add(nouvelle_annonce)
            db.session.commit()
            sync_annonce(nouvelle_annonce)
            flash('Annonce créée avec succès!', 'success')
            return redirect(url_for('annonces'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'danger')
    
    # Pré-remplir le type si spécifié dans l'URL
    if request.method == 'GET':
        annonce = Annonce(type_annonce=type)
    
    return render_template('edit_annonce.html', annonce=annonce)

@app.route('/annonce/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_annonce(id):
    annonce = Annonce.query.get_or_404(id)
    
    if request.method == 'POST':
        annonce.titre = request.form.get('titre')
        annonce.type_annonce = request.form.get('type_annonce')
        annonce.contenu = request.form.get('contenu')
        annonce.est_active = request.form.get('est_active') == 'true'
        
        date_debut_str = request.form.get('date_debut')
        date_fin_str = request.form.get('date_fin')
        
        if date_debut_str:
            annonce.date_debut = datetime.strptime(date_debut_str, '%Y-%m-%dT%H:%M')
        else:
            annonce.date_debut = None
            
        if date_fin_str:
            annonce.date_fin = datetime.strptime(date_fin_str, '%Y-%m-%dT%H:%M')
        else:
            annonce.date_fin = None
        
        try:
            db.session.commit()
            sync_annonce(annonce)
            flash('Annonce modifiée avec succès!', 'success')
            return redirect(url_for('annonces'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'danger')
    
    return render_template('edit_annonce.html', annonce=annonce)

@app.route('/annonce/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_annonce(id):
    annonce = Annonce.query.get_or_404(id)
    
    try:
        db.session.delete(annonce)
        db.session.commit()
        sync_delete('annonce', id)
        flash('Annonce supprimée avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'danger')
    
    return redirect(url_for('annonces'))

@app.route('/annonce/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_annonce(id):
    annonce = Annonce.query.get_or_404(id)
    annonce.est_active = not annonce.est_active
    
    try:
        db.session.commit()
        sync_annonce(annonce)
        status = "activée" if annonce.est_active else "désactivée"
        flash(f'Annonce {status} avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'danger')
    
    return redirect(url_for('annonces'))

# Routes pour les offres
@app.route('/offres')
@login_required
def offres():
    offres_list = Offre.query.order_by(Offre.date_creation.desc()).all()
    return render_template('offres.html', offres=offres_list, now=datetime.utcnow())

@app.route('/offre/nouvelle', methods=['GET', 'POST'])
@app.route('/offre/nouvelle/<string:type>', methods=['GET', 'POST'])
@login_required
def nouvelle_offre(type='emploi'):
    offre = None
    if request.method == 'POST':
        titre = request.form.get('titre')
        type_offre = request.form.get('type_offre')
        description = request.form.get('description')
        lieu = request.form.get('lieu')
        date_limite_str = request.form.get('date_limite')
        est_active = request.form.get('est_active') == 'true'
        
        date_limite = None
        if date_limite_str:
            date_limite = datetime.strptime(date_limite_str, '%Y-%m-%d').date()
        
        nouvelle_offre = Offre(
            titre=titre,
            type_offre=type_offre,
            description=description,
            lieu=lieu,
            date_limite=date_limite,
            est_active=est_active,
            date_creation=datetime.utcnow()
        )
        
        try:
            db.session.add(nouvelle_offre)
            db.session.commit()
            sync_offre(nouvelle_offre)
            flash('Offre créée avec succès!', 'success')
            return redirect(url_for('offres'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'danger')
    
    # Pré-remplir le type si spécifié dans l'URL
    if request.method == 'GET':
        offre = Offre(type_offre=type)
    
    return render_template('edit_offre.html', offre=offre)

@app.route('/offre/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_offre(id):
    offre = Offre.query.get_or_404(id)
    
    if request.method == 'POST':
        offre.titre = request.form.get('titre')
        offre.type_offre = request.form.get('type_offre')
        offre.description = request.form.get('description')
        offre.lieu = request.form.get('lieu')
        offre.est_active = request.form.get('est_active') == 'true'
        
        date_limite_str = request.form.get('date_limite')
        if date_limite_str:
            offre.date_limite = datetime.strptime(date_limite_str, '%Y-%m-%d').date()
        else:
            offre.date_limite = None
        
        try:
            db.session.commit()
            sync_offre(offre)
            flash('Offre modifiée avec succès!', 'success')
            return redirect(url_for('offres'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'danger')
    
    return render_template('edit_offre.html', offre=offre)

@app.route('/offre/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_offre(id):
    offre = Offre.query.get_or_404(id)
    
    try:
        db.session.delete(offre)
        db.session.commit()
        sync_delete('offre', id)
        flash('Offre supprimée avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'danger')
    
    return redirect(url_for('offres'))

@app.route('/offre/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_offre(id):
    offre = Offre.query.get_or_404(id)
    offre.est_active = not offre.est_active
    
    try:
        db.session.commit()
        sync_offre(offre)
        status = "activée" if offre.est_active else "désactivée"
        flash(f'Offre {status} avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'danger')
    
    return redirect(url_for('offres'))

# Fonctions de synchronisation
def sync_activite(activite):
    """Synchronise une activité avec le site principal"""
    try:
        data = {
            'titre': activite.titre,
            'description': activite.description,
            'contenu': activite.contenu,
            'image_url': activite.image_url,
            'auteur': activite.auteur,
            'date_creation': activite.date_creation.isoformat() if activite.date_creation else None,
            'api_key': API_KEY
        }
        
        if activite.id:
            data['id'] = activite.id
            response = requests.post(f'{SITE_URL}/api/activites/update', json=data)
        else:
            response = requests.post(f'{SITE_URL}/api/activites/create', json=data)
            
        return response.status_code == 200
    except Exception as e:
        print(f"Erreur de synchronisation activité: {e}")
        return False

def sync_realisation(realisation):
    """Synchronise une réalisation avec le site principal"""
    try:
        data = {
            'titre': realisation.titre,
            'description': realisation.description,
            'image_url': realisation.image_url,
            'categorie': realisation.categorie,
            'date_realisation': realisation.date_realisation.isoformat() if realisation.date_realisation else None,
            'api_key': API_KEY
        }
        
        if realisation.id:
            data['id'] = realisation.id
            response = requests.post(f'{SITE_URL}/api/realisations/update', json=data)
        else:
            response = requests.post(f'{SITE_URL}/api/realisations/create', json=data)
            
        return response.status_code == 200
    except Exception as e:
        print(f"Erreur de synchronisation réalisation: {e}")
        return False

def sync_annonce(annonce):
    """Synchronise une annonce avec le site principal"""
    try:
        data = {
            'titre': annonce.titre,
            'contenu': annonce.contenu,
            'type_annonce': annonce.type_annonce,
            'date_debut': annonce.date_debut.isoformat() if annonce.date_debut else None,
            'date_fin': annonce.date_fin.isoformat() if annonce.date_fin else None,
            'est_active': annonce.est_active,
            'api_key': API_KEY
        }
        
        if annonce.id:
            data['id'] = annonce.id
            response = requests.post(f'{SITE_URL}/api/annonces/update', json=data)
        else:
            response = requests.post(f'{SITE_URL}/api/annonces/create', json=data)
            
        return response.status_code == 200
    except Exception as e:
        print(f"Erreur de synchronisation annonce: {e}")
        return False

def sync_offre(offre):
    """Synchronise une offre avec le site principal"""
    try:
        data = {
            'titre': offre.titre,
            'description': offre.description,
            'type_offre': offre.type_offre,
            'lieu': offre.lieu,
            'date_limite': offre.date_limite.isoformat() if offre.date_limite else None,
            'est_active': offre.est_active,
            'api_key': API_KEY
        }
        
        if offre.id:
            data['id'] = offre.id
            response = requests.post(f'{SITE_URL}/api/offres/update', json=data)
        else:
            response = requests.post(f'{SITE_URL}/api/offres/create', json=data)
            
        return response.status_code == 200
    except Exception as e:
        print(f"Erreur de synchronisation offre: {e}")
        return False

def sync_delete(type_objet, id):
    """Synchronise la suppression avec le site principal"""
    try:
        data = {
            'type': type_objet,
            'id': id,
            'api_key': API_KEY
        }
        
        response = requests.post(f'{SITE_URL}/api/delete', json=data)
        return response.status_code == 200
    except Exception as e:
        print(f"Erreur de synchronisation suppression: {e}")
        return False

# Création des tables
def create_tables():
    with app.app_context():
        db.create_all()
        print("✅ Tables créées avec succès!")

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    create_tables()
    app.run(debug=os.environ.get('FLASK_ENV') == 'development', port=5001)