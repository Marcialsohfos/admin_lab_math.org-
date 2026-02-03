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
            date_realisation = datetime.strptime(date_realisation_str, '%Y-%m-%d')
        
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
            
            # Synchroniser avec le site principal
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
            realisation.date_realisation = datetime.strptime(date_realisation_str, '%Y-%m-%d')
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
            date_limite = datetime.strptime(date_limite_str, '%Y-%m-%d')
        
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
            offre.date_limite = datetime.strptime(date_limite_str, '%Y-%m-%d')
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

# Fonctions de synchronisation supplémentaires
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