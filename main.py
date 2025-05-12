import os
import re
from datetime import datetime
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from flask import Flask, render_template_string, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import logging
# Pas besoin de 'import csv'

# --- Initialisation de l'application Flask ---
app = Flask(__name__)

# --- Configuration du Logger ---
app.logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s')
console_handler.setFormatter(console_formatter)
if not app.logger.handlers:
    app.logger.addHandler(console_handler)

# --- Configuration Générale et de l'Upload ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'data')
SUGGESTIONS_TXT_FILE = os.path.join(BASE_DIR, 'suggestions.txt') # Fichier TXT pour les suggestions
ALLOWED_EXTENSIONS = {'xlsx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['SECRET_KEY'] = "MEHDARY_MEHDI_OFPPT_DASH_#2024_TXT_SUGGEST" # Changez ceci

if not os.path.exists(UPLOAD_FOLDER):
    try: os.makedirs(UPLOAD_FOLDER); app.logger.info(f"Dossier d'upload '{UPLOAD_FOLDER}' créé.")
    except OSError as e: app.logger.error(f"Impossible de créer dossier '{UPLOAD_FOLDER}': {e}")

# --- Fonctions Utilitaires ---
def allowed_file(filename): # ... (identique)
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['POST'])
def upload_file(): # ... (identique)
    if 'file' not in request.files: flash('Aucun fichier sélectionné.', 'warning'); return redirect(url_for('dashboard_page'))
    file = request.files['file']
    if file.filename == '': flash('Aucun fichier sélectionné.', 'warning'); return redirect(url_for('dashboard_page'))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename); file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        try: file.save(file_path); flash(f'Fichier "{filename}" uploadé ! Actualisation.', 'success'); app.logger.info(f"Fichier '{filename}' sauvegardé: {file_path}")
        except Exception as e_save: app.logger.error(f"Err sauvegarde upload: {e_save}", exc_info=True); flash(f'Erreur sauvegarde: {e_save}', 'danger')
        return redirect(url_for('dashboard_page'))
    else: flash('Type de fichier non autorisé (.xlsx seulement).', 'danger'); return redirect(url_for('dashboard_page'))

@app.route('/submit_suggestion', methods=['POST'])
def submit_suggestion(): # MODIFIÉ POUR FICHIER TXT SIMPLE ET SANS RATING
    nom = request.form.get('nom_suggestion_simple', 'Anonyme').strip() # Nouveau nom de champ
    message_text = request.form.get('message_suggestion_simple', '').strip() # Nouveau nom de champ

    if not message_text:
        flash('Le champ message ne peut pas être vide.', 'warning')
        return redirect(url_for('dashboard_page', show_suggestion_form='true')) # Garder le formulaire affiché
    if not nom: nom = "Anonyme"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    suggestion_entry = f"Date/Heure: {timestamp}\nNom: {nom}\nMessage: {message_text}\n--------------------\n\n"
    
    try:
        with open(SUGGESTIONS_TXT_FILE, 'a', encoding='utf-8') as f:
            f.write(suggestion_entry)
        flash('Merci pour votre message !', 'success')
        app.logger.info(f"Message de '{nom}' enregistré dans {SUGGESTIONS_TXT_FILE}.")
    except Exception as e_suggest:
        app.logger.error(f"Erreur lors de l'écriture du fichier de suggestions (txt): {e_suggest}", exc_info=True)
        flash('Erreur lors de l\'enregistrement de votre message.', 'danger')
        return redirect(url_for('dashboard_page', show_suggestion_form='true')) # Garder le formulaire en cas d'erreur serveur
    
    return redirect(url_for('dashboard_page')) # Redirige et cache le formulaire

def get_latest_file(directory, pattern): # ... (identique à v2.13)
    try:
        search_paths = [directory]; data_subdir_abs = os.path.join(BASE_DIR, 'data')
        if os.path.isdir(data_subdir_abs) and directory != data_subdir_abs : search_paths.append(data_subdir_abs)
        all_found_files = []
        for path_to_search in list(set(search_paths)):
            if os.path.isdir(path_to_search): all_found_files.extend([os.path.join(path_to_search, f) for f in os.listdir(path_to_search) if re.match(pattern, f, re.IGNORECASE) and f.lower().endswith('.xlsx')])
        if not all_found_files: raise FileNotFoundError(f"Aucun fichier Excel (pattern: '{pattern}') dans {search_paths}.")
        latest_file_full_path = max(all_found_files, key=os.path.getmtime); app.logger.info(f"Fichier Excel sélectionné: {latest_file_full_path}"); return latest_file_full_path
    except Exception as e: app.logger.error(f"Erreur recherche fichier: {e}", exc_info=True); raise

def robust_numeric_conversion(series, col_name_log=""): # ... (identique à v2.13)
    if series is None or not hasattr(series, 'empty') or series.empty or series.isnull().all():
        idx = series.index if series is not None and hasattr(series, 'index') else None; return pd.Series([0.0] * len(series if series is not None else []), index=idx, dtype='float64')
    if pd.api.types.is_numeric_dtype(series): return series.fillna(0.0)
    cleaned_series = series.copy(); cleaned_series.replace(['-', ' ', '', 'nan', 'None', 'NULL', '#N/A', 'N/A', 'non renseigné', 'Non renseigné'], np.nan, inplace=True)
    if cleaned_series.notnull().any():
        cleaned_series_str = cleaned_series.astype(str).str.replace(',', '.', regex=False).str.strip()
        cleaned_series_str.replace(['', 'nan', 'None'], np.nan, inplace=True); cleaned_series = cleaned_series_str
    numeric_series = pd.to_numeric(cleaned_series, errors='coerce')
    failed_mask = numeric_series.isnull() & cleaned_series.notnull()
    if failed_mask.any(): app.logger.warning(f"Conv. '{col_name_log}': {failed_mask.sum()} val. non converties. Ex: {list(cleaned_series[failed_mask].unique()[:3])}")
    final_series = numeric_series.fillna(0.0); app.logger.info(f"Conv. '{col_name_log}': Somme finale = {final_series.sum():.2f}"); return final_series

# --- Nettoyage et Préparation des Données ---
def clean_and_prepare_data(df_input): # ... (identique à v2.13)
    if not isinstance(df_input, pd.DataFrame) or df_input.empty: return pd.DataFrame()
    app.logger.info(f"DataFrame initial: {df_input.shape[0]}L, {df_input.shape[1]}C.")
    original_columns_from_excel = df_input.columns.tolist()
    column_mapping_config = {
        'Groupe': [r'^Groupe$'], 'Formateur_Nom': [r'^Formateur Affecté Présentiel Actif$'],
        'Matricule_Ou_CIN_Formateur': [r'^Mle Affecté Présentiel Actif$'], 'Effectif': [r'^Effectif Groupe$'],
        'MH_Totale_DRIF': [r'^MH Totale DRIF$', r'MH.*Totale.*DRIF'], 'Régional': [r'^Régional$'],
        'Filière': [r'^filière$'], 'Module': [r'^Module$'], 'Code_Module': [r'^Code Module$'],
        'Type_formation': [r'^Type de formation$'], 'EFM_Seance_Planifiee': [r'^Séance EFM$'], 
        'EFM_Notes_Saisies': [r'^Validation EFM$'],
        'MH_Affectee_Module': [r'^MH Affectée Globale \(P & SYN\)$', r'^MH Affectée Présentiel$'],
        'MH_Realisee_Module_Brute': [r'^MH Réalisée Globale$', r'^MH Réalisée Présentiel$'],
        'MH_Totale_S1_DRIF': [r'^MH Totale S1 DRIF$', r'MH.*S1.*DRIF'],
        'MH_Totale_S2_DRIF': [r'^MH Totale S2 DRIF$', r'MH.*S2.*DRIF'],
        'Taux_Realisation_Original_File': [r'^Taux Réalisation \(P & SYN\)$'], 'Secteur': [r'^Secteur$']}
    df = pd.DataFrame(index=df_input.index)
    for std_name, patterns in column_mapping_config.items():
        mapped_successfully = False
        for pattern_str in patterns:
            try:
                for original_col_excel in original_columns_from_excel:
                    col_excel_stripped = str(original_col_excel).strip()
                    if re.fullmatch(pattern_str, col_excel_stripped, re.IGNORECASE):
                        df[std_name] = df_input[original_col_excel].copy(); mapped_successfully = True; app.logger.debug(f"  OK (Fullmatch): '{std_name}' <- Excel:'{original_col_excel}'"); break
                    elif re.match(pattern_str, col_excel_stripped, re.IGNORECASE) and not mapped_successfully :
                        df[std_name] = df_input[original_col_excel].copy(); mapped_successfully = True; app.logger.debug(f"  OK (Match Partiel): '{std_name}' <- Excel:'{original_col_excel}'"); break
                if mapped_successfully: break
            except Exception as e_map: app.logger.error(f"  Err map '{std_name}' (pat '{pattern_str}'): {e_map}", exc_info=True)
        if not mapped_successfully: df[std_name] = np.nan; app.logger.warning(f"  ECHEC MAP: '{std_name}' non trouvé.")
    if 'Matricule_Ou_CIN_Formateur' not in df.columns: df['Matricule_Ou_CIN_Formateur'] = ""
    df['Matricule_Ou_CIN_Formateur'] = df['Matricule_Ou_CIN_Formateur'].astype(str).str.strip().replace({'nan': '', 'None': ''})
    numeric_cols = ['MH_Totale_DRIF', 'Effectif', 'MH_Affectee_Module', 'MH_Realisee_Module_Brute','MH_Totale_S1_DRIF', 'MH_Totale_S2_DRIF', 'Taux_Realisation_Original_File']
    for col in numeric_cols:
        if col in df.columns: df[col] = robust_numeric_conversion(df[col].copy(), col_name_log=col)
        else: df[col] = 0.0; app.logger.warning(f"  Col. num. '{col}' absente. Init 0.")
    cat_cols_config = [('Régional', {'O': 'Oui', 'N': 'Non', 'OUI':'Oui', 'NON':'Non'}, 'Non défini'), ('EFM_Seance_Planifiee', {'OUI':'Oui', 'NON':'Non', 'O':'Oui', 'N':'Non'}, 'Non défini'), ('EFM_Notes_Saisies', {'OUI':'Oui', 'NON':'Non', 'O':'Oui', 'N':'Non'}, 'Non défini'), ('Secteur', {}, 'Secteur Non Défini')] 
    for col_cat, map_dict, default_val in cat_cols_config:
        if col_cat in df.columns:
            df[col_cat] = df[col_cat].astype(str).str.strip().replace({'nan': default_val, 'None': default_val, '': default_val, 'NON RENSEIGNÉ': default_val})
            if map_dict: df[col_cat] = df[col_cat].str.upper().map(map_dict).fillna(default_val)
            df[col_cat] = df[col_cat].fillna(default_val); app.logger.debug(f"Col cat '{col_cat}' uniques: {list(df[col_cat].unique())}")
        else: df[col_cat] = default_val; app.logger.warning(f"Col cat '{col_cat}' non trouvée. Init '{default_val}'.")
    def determine_type_formateur(mle_cin_str):
        if not mle_cin_str or mle_cin_str.lower() in ['nan', 'none', 'n/a', '']: return "Non défini"
        if re.match(r'^[A-Za-z]{1,2}\d+$', mle_cin_str) or re.match(r'^[A-Za-z]+\d*$', mle_cin_str): return "Vacataire"
        elif re.match(r'^\d+$', mle_cin_str): return "Permanent"
        else: return "Indéterminé"
    df['Type_Formateur'] = df['Matricule_Ou_CIN_Formateur'].apply(determine_type_formateur)
    df['Formateur_Nom'] = df.get('Formateur_Nom', pd.Series("", index=df.index, dtype=str)).fillna("").astype(str).str.strip()
    df['Formateur_Identifiant_Pour_Compte'] = df['Matricule_Ou_CIN_Formateur'] + "_" + df['Formateur_Nom']
    df['Formateur_Identifiant_Pour_Compte'] = df['Formateur_Identifiant_Pour_Compte'].replace({'_N/A':'ID_Manquant', 'N/A_':'ID_Manquant', '_':'ID_Manquant', 'nan_nan':'ID_Manquant', '_nan':'ID_Manquant', 'nan_':'ID_Manquant'})
    mh_aff_mod_col = df.get('MH_Affectee_Module', pd.Series(0.0, index=df.index, dtype='float64'))
    mh_real_brute_col = df.get('MH_Realisee_Module_Brute', pd.Series(0.0, index=df.index, dtype='float64'))
    df['MH_Realisee_Module_Plafonnee'] = np.minimum(mh_real_brute_col, mh_aff_mod_col)
    df['Taux_Realisation'] = 0.0
    mask_calc = (mh_aff_mod_col > 1e-6) & mh_aff_mod_col.notna() & df['MH_Realisee_Module_Plafonnee'].notna()
    if mask_calc.any(): df.loc[mask_calc, 'Taux_Realisation'] = (df['MH_Realisee_Module_Plafonnee'][mask_calc] / mh_aff_mod_col[mask_calc]) * 100
    df['Taux_Realisation'] = df.get('Taux_Realisation', pd.Series(dtype='float64')).clip(0, 100).round(1)
    mh_tot_drif = df.get('MH_Totale_DRIF', pd.Series(0.0, index=df.index, dtype='float64'))
    mh_s1_drif = df.get('MH_Totale_S1_DRIF', pd.Series(0.0, index=df.index, dtype='float64'))
    mh_s2_drif = df.get('MH_Totale_S2_DRIF', pd.Series(0.0, index=df.index, dtype='float64'))
    df['Proportion_S1_DRIF'] = 0.0; df['Proportion_S2_DRIF'] = 0.0
    mask_drif_gt0 = mh_tot_drif > 1e-6
    if mask_drif_gt0.any():
        df.loc[mask_drif_gt0, 'Proportion_S1_DRIF'] = (mh_s1_drif[mask_drif_gt0] / mh_tot_drif[mask_drif_gt0]).fillna(0.0).clip(0,1)
        df.loc[mask_drif_gt0, 'Proportion_S2_DRIF'] = (mh_s2_drif[mask_drif_gt0] / mh_tot_drif[mask_drif_gt0]).fillna(0.0).clip(0,1)
    sum_props = df['Proportion_S1_DRIF'] + df['Proportion_S2_DRIF']
    mask_sum_gt0 = sum_props > 1e-6
    if mask_sum_gt0.any(): df.loc[mask_sum_gt0, 'Proportion_S1_DRIF'] /= sum_props[mask_sum_gt0]; df.loc[mask_sum_gt0, 'Proportion_S2_DRIF'] /= sum_props[mask_sum_gt0]
    df['MH_Affectee_S1_Estimee'] = (mh_aff_mod_col * df['Proportion_S1_DRIF']).round(2)
    df['MH_Affectee_S2_Estimee'] = (mh_aff_mod_col - df['MH_Affectee_S1_Estimee']).round(2)
    df.loc[df['MH_Affectee_S2_Estimee'] < 0, 'MH_Affectee_S2_Estimee'] = 0.0
    df['MH_Realisee_S1_Estimee'] = np.minimum(df.get('MH_Realisee_Module_Plafonnee', pd.Series(0.0, index=df.index)), df['MH_Affectee_S1_Estimee'])
    rest_apres_s1 = df.get('MH_Realisee_Module_Plafonnee', pd.Series(0.0, index=df.index)) - df['MH_Realisee_S1_Estimee']
    df['MH_Realisee_S2_Estimee'] = np.minimum(rest_apres_s1, df['MH_Affectee_S2_Estimee'])
    df['Taux_Realisation_S1_Estime'] = 0.0
    mask_s1_aff_gt0 = df.get('MH_Affectee_S1_Estimee', pd.Series(dtype='float64')) > 1e-6
    if mask_s1_aff_gt0.any(): df.loc[mask_s1_aff_gt0, 'Taux_Realisation_S1_Estime'] = (df['MH_Realisee_S1_Estimee'][mask_s1_aff_gt0] / df['MH_Affectee_S1_Estimee'][mask_s1_aff_gt0]) * 100
    df['Taux_Realisation_S1_Estime'] = df['Taux_Realisation_S1_Estime'].clip(0, 100).round(1)
    df['Est_S1_Non_Acheve'] = (df.get('MH_Affectee_S1_Estimee', pd.Series(dtype='float64')) > 1e-6) & (df['Taux_Realisation_S1_Estime'] < 99.9)
    df['Est_S2_Entame'] = df.get('MH_Realisee_S2_Estimee', pd.Series(dtype='float64')) > 1e-6
    app.logger.debug(f"--- Vérification Détail Colonnes Booléennes Alerte S1/S2 ---"); app.logger.debug(f"  Somme Est_S1_Non_Acheve: {df['Est_S1_Non_Acheve'].sum()}"); app.logger.debug(f"  Somme Est_S2_Entame: {df['Est_S2_Entame'].sum()}")
    if df['Est_S1_Non_Acheve'].any(): app.logger.debug(f"  Ex S1 Non Achevés:\n{df[df['Est_S1_Non_Acheve']][['Formateur_Nom', 'Code_Module', 'Groupe', 'MH_Affectee_S1_Estimee', 'Taux_Realisation_S1_Estime']].head().to_string()}")
    else: app.logger.debug("  Aucune ligne trouvée avec Est_S1_Non_Acheve = True")
    if df['Est_S2_Entame'].any(): app.logger.debug(f"  Ex S2 Entamés:\n{df[df['Est_S2_Entame']][['Formateur_Nom', 'Code_Module', 'Groupe', 'MH_Realisee_S2_Estimee']].head().to_string()}")
    else: app.logger.debug("  Aucune ligne trouvée avec Est_S2_Entame = True")
    app.logger.debug(f"--- Fin Vérification Détail Colonnes Booléennes ---")
    string_cols_ensure = ['Groupe', 'Formateur_Nom', 'Filière', 'Module', 'Code_Module', 'Secteur', 'Type_formation', 'Type_Formateur', 'Matricule_Ou_CIN_Formateur', 'Formateur_Identifiant_Pour_Compte', 'EFM_Seance_Planifiee', 'EFM_Notes_Saisies']
    for col in string_cols_ensure:
        if col not in df.columns: df[col] = "N/A"
        else: df[col] = df[col].astype(str).replace({'nan': 'N/A', 'None': 'N/A', '': 'N/A'}).fillna("N/A")
    app.logger.info(f"Nettoyage terminé. DataFrame final: {df.shape[0]}L.")
    return df

# --- create_visualizations (Identique à v2.12) ---
def create_visualizations(df): # ... (Copier le code complet de create_visualizations de la v2.12 ici)
    graphs = {}
    default_graph_msg = "<div class='alert alert-light text-center p-3 border small'>Données insuffisantes ou manquantes.</div>"
    if df.empty: 
        graph_keys_on_empty = ['avancement_groupe', 'avancement_formateur', 'regional', 'statut_efm', 'repartition_type_formateur', 'charge_horaire_s1s2_formateur_horizontal'] 
        for key in graph_keys_on_empty: graphs[key] = default_graph_msg
        return graphs
    try: 
        df_g = df.copy()
        if 'Groupe' in df_g.columns and 'Taux_Realisation' in df_g.columns and df_g['Groupe'].notna().any() and df_g['Groupe'].nunique() > 0 :
            data = df_g.groupby('Groupe')['Taux_Realisation'].mean().reset_index()
            data = data[data['Taux_Realisation'] >= 0].sort_values('Taux_Realisation', ascending=False) 
            if not data.empty:
                num_items = len(data['Groupe']); bar_height_px = max(15, 40 - num_items // 3); graph_height = max(350, num_items * bar_height_px + 150)
                fig = px.bar(data, y='Groupe', x='Taux_Realisation', title='<b>Avancement par Groupe</b>', orientation='h', color='Taux_Realisation', color_continuous_scale='RdYlGn', range_color=[0,100], text='Taux_Realisation', height=graph_height)
                fig.update_traces(texttemplate='%{x:.1f}%', textposition='outside', marker_line_color='rgb(8,48,107)', marker_line_width=0.8, opacity=0.9)
                fig.update_layout(yaxis_title=None, xaxis_title='Taux de Réalisation (%)', xaxis_ticksuffix='%', xaxis_range=[0,115], yaxis={'categoryorder':'total descending', 'tickfont': {'size': 9}}, coloraxis_showscale=False, margin=dict(l=160, r=30, t=60, b=40), title_x=0.5, font=dict(size=10))
                graphs['avancement_groupe'] = fig.to_html(full_html=False)
            else: graphs['avancement_groupe'] = default_graph_msg
        else: graphs['avancement_groupe'] = default_graph_msg
    except Exception as e: app.logger.error(f"Err graph 'avancement_groupe': {e}", exc_info=True); graphs['avancement_groupe'] = f"<div class='alert alert-danger small'>Erreur: {e}</div>"
    try: 
        df_f = df.copy()
        if ('Formateur_Nom' in df_f.columns and df_f['Formateur_Nom'].notna().any() and  df_f['Formateur_Nom'].nunique() > 0 and 'Taux_Realisation' in df_f.columns and 'Module' in df_f.columns and 'Est_S1_Non_Acheve' in df_f.columns and 'Est_S2_Entame' in df_f.columns):
            df_f_filtered = df_f[(df_f['Formateur_Nom'] != "N/A") & (df_f['Formateur_Nom'] != "")]
            formateur_summary = df_f_filtered.groupby('Formateur_Nom').agg(
                Taux_Realisation_Moyen=('Taux_Realisation', 'mean'), Nb_S1_Non_Acheve=('Est_S1_Non_Acheve', 'sum'), Nb_S2_Entame=('Est_S2_Entame', 'sum'),
                Noms_Modules_S1_NA_Tooltip = ('Module', lambda x: ', '.join(df_f_filtered.loc[x.index][df_f_filtered.loc[x.index]['Est_S1_Non_Acheve']]['Module'].unique()[:2]) + ('...' if df_f_filtered.loc[x.index][df_f_filtered.loc[x.index]['Est_S1_Non_Acheve']]['Module'].nunique() > 2 else '')),
                Noms_Modules_S2_Ent_Tooltip = ('Module', lambda x: ', '.join(df_f_filtered.loc[x.index][df_f_filtered.loc[x.index]['Est_S2_Entame']]['Module'].unique()[:2]) + ('...' if df_f_filtered.loc[x.index][df_f_filtered.loc[x.index]['Est_S2_Entame']]['Module'].nunique() > 2 else ''))
            ).reset_index()
            data = formateur_summary.sort_values('Taux_Realisation_Moyen', ascending=False)
            if not data.empty:
                num_items_f = len(data['Formateur_Nom']); bar_height_px_f = max(15, 40 - num_items_f // 3); graph_height_f = max(350, num_items_f * bar_height_px_f + 150)
                fig = px.bar(data, y='Formateur_Nom', x='Taux_Realisation_Moyen', title='<b>Avancement par Formateur</b>', orientation='h', color='Taux_Realisation_Moyen', color_continuous_scale=px.colors.sequential.Viridis, range_color=[0,100], text='Taux_Realisation_Moyen', height=graph_height_f, custom_data=['Nb_S1_Non_Acheve', 'Nb_S2_Entame', 'Noms_Modules_S1_NA_Tooltip', 'Noms_Modules_S2_Ent_Tooltip'])
                fig.update_traces(texttemplate='%{x:.1f}%', textposition='outside', marker_line_color='rgb(8,48,107)', marker_line_width=0.8, opacity=0.9, hovertemplate=("<b>%{y}</b><br>Taux Global: %{x:.1f}%<br>" + "S1 Non Achevés: %{customdata[0]} {% if customdata[2] and customdata[2] != '...' %}(Modules: {{customdata[2]}}){% endif %}<br>" + "S2 Entamés: %{customdata[1]} {% if customdata[3] and customdata[3] != '...' %}(Modules: {{customdata[3]}}){% endif %}<extra></extra>"))
                fig.update_layout(yaxis_title=None, xaxis_title='Taux de Réal. Moyen (%)', xaxis_ticksuffix='%', xaxis_range=[0,115], yaxis={'categoryorder':'total descending', 'tickfont': {'size': 9}}, coloraxis_showscale=False, margin=dict(l=180, r=20, t=60, b=40), title_x=0.5, font=dict(size=10))
                graphs['avancement_formateur'] = fig.to_html(full_html=False)
            else: graphs['avancement_formateur'] = default_graph_msg
        else: graphs['avancement_formateur'] = default_graph_msg
    except Exception as e: app.logger.error(f"Err graph 'avancement_formateur': {e}", exc_info=True); graphs['avancement_formateur'] = f"<div class='alert alert-danger small'>Erreur: {e}</div>"
    pie_charts_config = [
        {'key': 'regional', 'column': 'Régional', 'title': '<b>Modules Régionaux</b>', 'colors': {'Oui': '#00a65a', 'Non': '#6c757d', 'Non défini': '#adb5bd'}},
        {'key': 'statut_efm', 'column': 'EFM_Notes_Saisies', 'title': '<b>Validation EFM (Notes)</b>', 'colors': {'Oui': '#28a745', 'Non': '#dc3545', 'Non renseigné': '#6c757d'}},
        {'key': 'repartition_type_formateur', 'column': 'Type_Formateur', 'title': '<b>Modules par Type Formateur</b>', 'colors': {'Permanent': '#0056b3', 'Vacataire': '#f39c12', 'Indéterminé':'#adb5bd', 'Non défini': '#6c757d'}}
    ]
    for config in pie_charts_config:
        try:
            df_pie = df.copy()
            if config['column'] in df_pie.columns and df_pie[config['column']].notna().any() and df_pie[config['column']].nunique() > 0:
                data = df_pie[config['column']].value_counts().reset_index(); data.columns = [config['column'], 'Nombre']
                if config['key'] == 'statut_efm': data = data[data[config['column']] != 'Non défini'] 
                if not data.empty:
                    fig = px.pie(data, names=config['column'], values='Nombre', title=config['title'], hole=0.4, color=config['column'], color_discrete_map=config.get('colors'), height=350)
                    fig.update_traces(textposition='inside', textinfo='percent+label+value', marker_line_color='white', marker_line_width=1)
                    fig.update_layout(showlegend=True, margin=dict(t=60, b=40, l=20, r=20), title_x=0.5, legend_font_size=10, legend=dict(orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5))
                    graphs[config['key']] = fig.to_html(full_html=False)
                else: graphs[config['key']] = default_graph_msg
            else: graphs[config['key']] = default_graph_msg
        except Exception as e: app.logger.error(f"Err graph '{config['key']}': {e}", exc_info=True); graphs[config['key']] = f"<div class='alert alert-danger small'>Erreur: {e}</div>"
    try: # Charge Horaire S1/S2 Estimée par Formateur
        df_charge_form = df.copy()
        if ('Formateur_Nom' in df_charge_form.columns and df_charge_form['Formateur_Nom'].notna().any() and 'MH_Affectee_S1_Estimee' in df_charge_form.columns and 'MH_Affectee_S2_Estimee' in df_charge_form.columns):
            df_charge_filt = df_charge_form[df_charge_form['Formateur_Nom'] != "N/A"]
            data_charge_agg = df_charge_filt.groupby('Formateur_Nom').agg(S1_Affectee=('MH_Affectee_S1_Estimee', 'sum'), S2_Affectee=('MH_Affectee_S2_Estimee', 'sum')).reset_index()
            data_charge_agg = data_charge_agg[(data_charge_agg['S1_Affectee'] > 0) | (data_charge_agg['S2_Affectee'] > 0)]
            data_charge_agg['Total_Charge_Pour_Tri'] = data_charge_agg['S1_Affectee'] + data_charge_agg['S2_Affectee']
            data_charge_agg = data_charge_agg.sort_values('Total_Charge_Pour_Tri', ascending=False).head(20)
            if not data_charge_agg.empty:
                fig = go.Figure()
                fig.add_trace(go.Bar(y=data_charge_agg['Formateur_Nom'], x=data_charge_agg['S1_Affectee'], name='MH Affectée S1 (Est.)', orientation='h', marker_color='rgb(26, 118, 255)', text=data_charge_agg['S1_Affectee'].apply(lambda x: f"{x:.0f}h" if x > 0 else "" ), textposition='auto'))
                fig.add_trace(go.Bar(y=data_charge_agg['Formateur_Nom'], x=data_charge_agg['S2_Affectee'], name='MH Affectée S2 (Est.)', orientation='h', marker_color='rgb(255, 127, 14)', text=data_charge_agg['S2_Affectee'].apply(lambda x: f"{x:.0f}h" if x > 0 else ""), textposition='auto'))
                fig.update_layout(title='<b>Charge Horaire Estimée S1/S2 par Formateur (Top 20)</b>', barmode='stack', yaxis_title=None, xaxis_title='Total Heures Affectées Estimées', height=max(400, len(data_charge_agg['Formateur_Nom']) * 30 + 150), margin=dict(l=180, r=20, t=80, b=40), title_x=0.5, legend_title_text='Semestre', yaxis={'categoryorder':'total descending'})
                graphs['charge_horaire_s1s2_formateur_horizontal'] = fig.to_html(full_html=False)
            else: graphs['charge_horaire_s1s2_formateur_horizontal'] = default_graph_msg
        else: graphs['charge_horaire_s1s2_formateur_horizontal'] = default_graph_msg
    except Exception as e: app.logger.error(f"Err graph 'charge_horaire_s1s2_formateur_horizontal': {e}", exc_info=True); graphs['charge_horaire_s1s2_formateur_horizontal'] = f"<div class='alert alert-danger small'>Erreur: {e}</div>"
    return graphs

# --- Route Principale et Calcul des KPIs ---
@app.route('/')
def dashboard_page():
    default_template_msg = "<div class='alert alert-warning text-center p-3 my-2'><strong>Attention:</strong> Données non disponibles ou insuffisantes.</div>"
    formateurs_s1_nonacheve_s2_entame_data = [] 
    formateurs_notes_en_attente_data = []
    modules_non_affectes_par_secteur = {} 
    show_suggestion_form_param = request.args.get('show_suggestion_form', 'false') # Pour garder le formulaire ouvert après erreur

    try:
        script_dir = os.path.dirname(os.path.abspath(__file__)); input_file = get_latest_file(script_dir, r"AvancementProgramme.*\.xlsx")
        df_source = pd.DataFrame()
        try:
            xls = pd.ExcelFile(input_file); sheet_to_read = None; preferred_sheet = 'AvancementProgramme'; norm_pref_sheet = ''.join(preferred_sheet.lower().split())
            found_sheet_name = next((s for s in xls.sheet_names if ''.join(s.lower().split()) == norm_pref_sheet), None)
            if found_sheet_name: sheet_to_read = found_sheet_name
            elif xls.sheet_names: sheet_to_read = xls.sheet_names[0]; app.logger.warning(f"Feuille '{preferred_sheet}' non trouvée. Lecture: '{sheet_to_read}'")
            if not sheet_to_read: raise Exception("Aucune feuille trouvée dans Excel.")
            app.logger.info(f"Lecture feuille '{sheet_to_read}' depuis '{input_file}'"); df_source = pd.read_excel(input_file, sheet_name=sheet_to_read)
        except Exception as e_read: app.logger.error(f"Erreur lecture Excel: {e_read}", exc_info=True); return render_template_string(f"""<!DOCTYPE html><html><head><title>Erreur Dashboard</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet"></head><body><div class="container mt-5"><div class="alert alert-danger"><h4>Erreur de Lecture du Fichier Excel</h4><p>Impossible de lire le fichier : {os.path.basename(input_file) if 'input_file' in locals() else 'Spécifié'}</p><p><small>{e_read}</small></p><a href="/" class="btn btn-primary mt-2">Réessayer</a></div></div></body></html>""", default_message=default_template_msg)
        df = clean_and_prepare_data(df_source.copy())
        kpis = {'date_analyse': datetime.now().strftime("%d/%m/%Y %H:%M"), 'fichier_utilise': os.path.basename(input_file), 'total_lignes_fichier': len(df_source)}
        if not df.empty:
            # ... (KPIs globaux, S1/S2, EFM, Type Formateur - comme avant)
            kpis['total_groupes'] = df.get('Groupe', pd.Series(dtype='object')).nunique(); kpis['total_formateurs'] = df.get('Formateur_Identifiant_Pour_Compte', pd.Series(dtype='object')).nunique(dropna=False); kpis['total_apprentis'] = int(df.get('Effectif', pd.Series(dtype='float64')).sum()); kpis['modules_regionaux_oui'] = df[df.get('Régional') == 'Oui'].shape[0] if 'Régional' in df.columns else 0
            kpis['mh_proposee_drif_totale'] = round(df.get('MH_Totale_DRIF', pd.Series(dtype='float64')).sum(), 1); kpis['mh_affectee_totale'] = round(df.get('MH_Affectee_Module', pd.Series(dtype='float64')).sum(), 1); kpis['mh_realisee_plafonnee_totale'] = round(df.get('MH_Realisee_Module_Plafonnee', pd.Series(dtype='float64')).sum(), 1); kpis['mh_realisee_brute_totale'] = round(df.get('MH_Realisee_Module_Brute', pd.Series(dtype='float64')).sum(), 1)
            mh_affectee = kpis.get('mh_affectee_totale', 0.0); mh_real_plaf = kpis.get('mh_realisee_plafonnee_totale', 0.0); kpis['taux_realisation_general_affecte'] = min(round((mh_real_plaf / mh_affectee * 100), 1), 100.0) if mh_affectee > 1e-6 else 0.0
            valid_taux = df.get('Taux_Realisation', pd.Series(dtype='float64')).dropna(); kpis['taux_realisation_moyen_module'] = round(valid_taux.mean(), 1) if not valid_taux.empty else 0.0
            total_affecte_s1_estimee = df.get('MH_Affectee_S1_Estimee', pd.Series(dtype='float64')).sum(); total_realise_s1_estimee = df.get('MH_Realisee_S1_Estimee', pd.Series(dtype='float64')).sum(); kpis['mh_affectee_s1_estimee'] = round(total_affecte_s1_estimee, 1); kpis['taux_s1'] = min(round((total_realise_s1_estimee / total_affecte_s1_estimee * 100), 1), 100.0) if total_affecte_s1_estimee > 1e-6 else 0.0
            total_affecte_s2_estimee = df.get('MH_Affectee_S2_Estimee', pd.Series(dtype='float64')).sum(); total_realise_s2_estimee = df.get('MH_Realisee_S2_Estimee', pd.Series(dtype='float64')).sum(); kpis['mh_affectee_s2_estimee'] = round(total_affecte_s2_estimee, 1); kpis['taux_s2'] = min(round((total_realise_s2_estimee / total_affecte_s2_estimee * 100), 1), 100.0) if total_affecte_s2_estimee > 1e-6 else 0.0
            if 'EFM_Seance_Planifiee' in df.columns and 'EFM_Notes_Saisies' in df.columns:
                kpis['efm_total_modules_pour_seance'] = len(df); kpis['efm_seances_oui'] = (df['EFM_Seance_Planifiee'] == 'Oui').sum(); kpis['efm_total_modules_pour_validation'] = kpis['efm_seances_oui']; kpis['efm_validation_oui'] = (df[df['EFM_Seance_Planifiee'] == 'Oui']['EFM_Notes_Saisies'] == 'Oui').sum(); kpis['taux_efm_validation'] = round((kpis['efm_validation_oui'] / kpis['efm_total_modules_pour_validation'] * 100), 1) if kpis['efm_total_modules_pour_validation'] > 0 else 0.0
            else: kpis.update({'efm_total_modules_pour_seance': 0, 'efm_seances_oui': 0, 'efm_total_modules_pour_validation': 0, 'efm_validation_oui': 0, 'taux_efm_validation': 0.0})
            if 'Type_Formateur' in df.columns and 'Formateur_Identifiant_Pour_Compte' in df.columns:
                kpis['formateurs_permanents'] = df[df['Type_Formateur'] == 'Permanent']['Formateur_Identifiant_Pour_Compte'].nunique(); kpis['formateurs_vacataires'] = df[df['Type_Formateur'] == 'Vacataire']['Formateur_Identifiant_Pour_Compte'].nunique(); kpis['mh_affectee_permanents'] = round(df[df['Type_Formateur'] == 'Permanent']['MH_Affectee_Module'].sum(), 1); kpis['mh_affectee_vacataires'] = round(df[df['Type_Formateur'] == 'Vacataire']['MH_Affectee_Module'].sum(), 1)
            else: kpis.update({'formateurs_permanents': 0, 'formateurs_vacataires': 0, 'mh_affectee_permanents':0.0, 'mh_affectee_vacataires':0.0})
            
            app.logger.debug("--- Début Préparation Tableau Alertes Formateurs S1 Non Achevés ET S2 Entamés (dashboard_page) ---")
            if 'Formateur_Nom' in df.columns and 'Code_Module' in df.columns and 'Groupe' in df.columns:
                df_copy_alerte = df.copy(); 
                if 'Est_S1_Non_Acheve' not in df_copy_alerte.columns: df_copy_alerte['Est_S1_Non_Acheve'] = False; app.logger.warning("Col 'Est_S1_Non_Acheve' manquante pour alerte formateur.")
                if 'Est_S2_Entame' not in df_copy_alerte.columns: df_copy_alerte['Est_S2_Entame'] = False; app.logger.warning("Col 'Est_S2_Entame' manquante pour alerte formateur.")
                for formateur, group_df in df_copy_alerte.groupby('Formateur_Nom'):
                    if formateur == "N/A" or formateur == "" or pd.isna(formateur): continue
                    a_modules_s1_non_acheves = group_df['Est_S1_Non_Acheve'].any(); a_modules_s2_entames = group_df['Est_S2_Entame'].any()
                    app.logger.debug(f"Formateur: {formateur} | a_S1_Non_Achevés: {a_modules_s1_non_acheves} | a_S2_Entamés: {a_modules_s2_entames}")
                    if a_modules_s1_non_acheves and a_modules_s2_entames:
                        app.logger.info(f"  OK! Formateur '{formateur}' correspond aux critères ET pour alertes S1/S2.")
                        s1_non_acheves_details = [f"({row['Groupe']}/{row['Code_Module']})" for _, row in group_df[group_df['Est_S1_Non_Acheve']].iterrows()]
                        s2_entames_details = [f"({row['Groupe']}/{row['Code_Module']})" for _, row in group_df[group_df['Est_S2_Entame']].iterrows()]
                        formateurs_s1_nonacheve_s2_entame_data.append({'nom': formateur, 's1_alerte_display': ", ".join(s1_non_acheves_details[:3]) + ('...' if len(s1_non_acheves_details) > 3 else ''), 's1_alerte_tooltip': ", ".join(s1_non_acheves_details) if s1_non_acheves_details else "Aucun", 's2_alerte_display': ", ".join(s2_entames_details[:3]) + ('...' if len(s2_entames_details) > 3 else ''), 's2_alerte_tooltip': ", ".join(s2_entames_details) if s2_entames_details else "Aucun", 'nb_s1_non_acheves': len(s1_non_acheves_details), 'nb_s2_entames': len(s2_entames_details)})
                formateurs_s1_nonacheve_s2_entame_data.sort(key=lambda x: (x['nb_s1_non_acheves'], x['nb_s2_entames']), reverse=True)
            app.logger.info(f"--- Fin Préparation Tableau Alertes S1/S2. {len(formateurs_s1_nonacheve_s2_entame_data)} formateurs trouvés. ---")

            if 'Formateur_Nom' in df.columns and 'Code_Module' in df.columns and 'Groupe' in df.columns and 'Taux_Realisation' in df.columns and 'EFM_Notes_Saisies' in df.columns:
                mask_notes_en_attente = (df['Taux_Realisation'] >= 97) & (df['EFM_Notes_Saisies'].isin(['Non', 'Non renseigné', 'N/A'])) & (df['Formateur_Nom'] != "N/A") & (df['Formateur_Nom'] != ""); df_notes_attente = df[mask_notes_en_attente]
                if not df_notes_attente.empty:
                    for _, row in df_notes_attente.iterrows(): formateurs_notes_en_attente_data.append({'formateur': row['Formateur_Nom'], 'code_module': row['Code_Module'], 'groupe': row['Groupe'], 'taux_realisation': row['Taux_Realisation']})
                    formateurs_notes_en_attente_data.sort(key=lambda x: (x['formateur'], -x['taux_realisation']))
            if 'Secteur' in df.columns and 'Code_Module' in df.columns and 'Groupe' in df.columns and 'MH_Affectee_Module' in df.columns:
                df_non_affectes = df[df['MH_Affectee_Module'] <= 0.1].copy(); df_non_affectes['Secteur'] = df_non_affectes['Secteur'].fillna('Secteur Non Défini'); df_non_affectes['Code_Module'] = df_non_affectes['Code_Module'].fillna('Code N/A'); df_non_affectes['Module'] = df_non_affectes['Module'].fillna('Module N/A'); df_non_affectes['Groupe'] = df_non_affectes['Groupe'].fillna('Groupe N/A')
                if not df_non_affectes.empty:
                    for secteur, group in df_non_affectes.groupby('Secteur'):
                        if secteur == "N/A" or secteur == "Secteur Non Défini": continue
                        modules_list = []
                        for _, row in group.iterrows(): nom_module_complet = row['Module'] ; nom_module_affiche = nom_module_complet[:30] + "..." if len(nom_module_complet) > 30 else nom_module_complet; modules_list.append({'groupe': row['Groupe'], 'code_module': row['Code_Module'], 'nom_module': nom_module_affiche, 'nom_module_complet': nom_module_complet})
                        if modules_list: modules_non_affectes_par_secteur[secteur] = sorted(modules_list, key=lambda x: (x['groupe'], x['code_module']))
            graphs = create_visualizations(df)
        else: # df est vide
            kpi_keys_to_default = ['total_groupes', 'total_formateurs', 'total_apprentis', 'modules_regionaux_oui','mh_proposee_drif_totale', 'mh_affectee_totale', 'mh_realisee_plafonnee_totale', 'mh_realisee_brute_totale', 'taux_realisation_general_affecte', 'taux_realisation_moyen_module', 'mh_affectee_s1_estimee', 'taux_s1', 'mh_affectee_s2_estimee', 'taux_s2', 'efm_total_modules_pour_seance', 'efm_seances_oui', 'efm_total_modules_pour_validation', 'efm_validation_oui', 'taux_efm_validation','formateurs_permanents', 'formateurs_vacataires', 'mh_affectee_permanents', 'mh_affectee_vacataires']
            for key in kpi_keys_to_default: kpis[key] = 0.0
            graph_keys = ['avancement_groupe', 'avancement_formateur', 'regional', 'statut_efm', 'repartition_type_formateur', 'charge_horaire_s1s2_formateur_horizontal']
            graphs = {key: default_template_msg for key in graph_keys}
        
        html_template = """
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Dashboard Pédagogique OFPPT v2.13</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.3.0/css/all.min.css">
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style> /* CSS identique à la version précédente */
                :root { --ofppt-blue: #0056b3; --ofppt-green: #00a65a; --ofppt-orange: #f39c12; --bs-primary: var(--ofppt-blue); --bs-success: var(--ofppt-green); --bs-warning: var(--ofppt-orange); --bs-body-bg: #f4f7f6; }
                body { display: flex; min-height: 100vh; font-family: 'Segoe UI', sans-serif; background-color: var(--bs-body-bg); }
                #sidebar { width: 320px; background-color: #fff; position: fixed; top: 0; left: 0; height: 100vh; overflow-y: auto; padding: 1.5rem 1rem; box-shadow: 0 0 15px rgba(0,0,0,0.1); z-index: 1030; display: flex; flex-direction: column; }
                #sidebar .sidebar-header { text-align: center; margin-bottom: 1rem; padding-bottom:1rem; border-bottom:1px solid #eee;}
                #sidebar .sidebar-header h3 { font-size: 1.3rem; color: var(--ofppt-blue); font-weight: 700;}
                #sidebar .sidebar-header .small {font-size:0.7em; color:#777;}
                #main-content { margin-left: 320px; padding: 1.5rem; width: calc(100% - 320px); }
                .kpi-group-title { font-weight: 600; margin-top: 0.6rem; margin-bottom: 0.3rem; color: var(--ofppt-green); font-size:0.8rem; border-bottom:1px solid #f0f0f0; padding-bottom:0.2rem; text-transform: uppercase; letter-spacing: 0.5px;}
                .kpi-item { display: flex; justify-content: space-between; align-items: center; padding: 0.2rem 0; font-size: 0.75rem;}
                .kpi-item .value { font-weight: 700; color: var(--ofppt-blue); font-size:0.8rem;} .kpi-item .label { color: #555;}
                .kpi-detailed-item { padding: 0.15rem 0; font-size: 0.75rem; margin-bottom: 0.2rem; }
                .kpi-detailed-item .label-main { color: #555; display: block; line-height:1.1; }
                .kpi-detailed-item .value-main { font-weight: 700; color: var(--ofppt-blue); font-size: 0.9rem; display: block; text-align: right; line-height:1.1;}
                .kpi-detailed-item .label-sub { font-size: 0.65rem; color: #777; display: block; text-align: right;}
                .progress { height: 5px; background-color: #e9ecef; border-radius:3px; margin-top:3px;} .progress-bar { background-color: var(--ofppt-green); }
                .graph-card { background-color: #fff; border-radius: 0.5rem; padding: 1rem; margin-bottom: 1.5rem; box-shadow: 0 2px 10px rgba(0,0,0,0.07); min-height:420px; display:flex; flex-direction:column; }
                .graph-card-small { background-color: #fff; border-radius: 0.5rem; padding: 0.8rem; margin-bottom: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.06); min-height:380px; display:flex; flex-direction:column; } 
                .graph-card .plotly-graph-div, .graph-card-small .plotly-graph-div { flex-grow:1; }
                .page-header { margin-bottom: 1.5rem; padding-bottom:1rem; border-bottom:2px solid var(--ofppt-green);}
                .page-header h1 {color: var(--ofppt-blue); font-weight:bold; font-size:1.7rem;} .page-header .text-muted {font-size:0.8rem;}
                #sidebarCollapse { display: none; position: fixed; top: 10px; left: 10px; z-index:1031; background-color: var(--ofppt-blue); border-color: var(--ofppt-blue); padding: 0.25rem 0.5rem; font-size:0.8rem;}
                @media (max-width: 992px) { #sidebar { margin-left: -320px; } #main-content { margin-left: 0; width:100%; padding: 1rem;} #sidebar.active { margin-left: 0; } #sidebarCollapse { display: block; } }
                .table-sm th, .table-sm td { font-size: 0.75rem; padding: 0.3rem;} .sticky-top {position: sticky; top: 0; z-index: 1020;} 
                .upload-suggestion-bar { background-color: #e9ecef; padding: 0.5rem 1rem; margin-bottom: 1.5rem; border-radius: 0.375rem; display: flex; justify-content: flex-end; align-items: center; flex-wrap: wrap; gap: 0.5rem;}
                .clickable-filename-label { cursor: pointer; color: var(--ofppt-blue); text-decoration: underline; }
                .clickable-filename-label:hover { color: var(--ofppt-orange); }
                #hidden-file-input { display: none; }
                /* Style pour le formulaire de suggestion caché */
                #suggestion-form-container { display: none; margin-top: 1rem; padding: 1rem; background-color: #fff; border-radius: 0.375rem; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            </style>
        </head>
        <body>
            <nav id="sidebar">
                <div class="sidebar-header">
                    <h3><i class="fas fa-chart-pie me-2"></i>Suivi Pédagogique</h3>
                    <div class="small text-muted">
                        <form action="{{ url_for('upload_file') }}" method="post" enctype="multipart/form-data" id="upload-form-sidebar" class="mb-1">
                            <input type="file" name="file" id="hidden-file-input" required accept=".xlsx" onchange="document.getElementById('upload-form-sidebar').submit();">
                            <label for="hidden-file-input" class="clickable-filename-label" title="Cliquez pour changer de fichier">
                                <i class="fas fa-file-excel me-1"></i> {{ kpis.get('fichier_utilise', 'N/A') }}
                            </label>
                        </form>
                        <i class="fas fa-sync me-1"></i> {{ kpis.get('date_analyse', 'N/A') }}
                    </div>
                </div>
                <!-- ... (Reste de la sidebar : KPIs - identique à v2.13) ... -->
                <div class="kpi-group-title">Vue d'Ensemble</div>
                <div class="kpi-item"><span class="label">Groupes</span> <span class="value">{{ kpis.get('total_groupes', 0) }}</span></div>
                <div class="kpi-item"><span class="label">Stagiaires</span> <span class="value">{{ kpis.get('total_apprentis', 0) }}</span></div>
                <div class="kpi-item"><span class="label">Modules Régionaux</span> <span class="value">{{ kpis.get('modules_regionaux_oui', 0) }}</span></div>
                <div class="kpi-group-title">Détail Formateurs</div> 
                <div class="kpi-item"><span class="label">Permanents</span> <span class="value">{{ kpis.get('formateurs_permanents', 0) }}</span></div>
                <div class="kpi-item"><span class="label">Vacataires</span> <span class="value">{{ kpis.get('formateurs_vacataires', 0) }}</span></div>
                <div class="kpi-detailed-item mt-2"><span class="label-main">MH Affectées Permanents</span><span class="value-main">{{ "%.1f" | format(kpis.get('mh_affectee_permanents', 0.0)) }}h</span></div>
                <div class="kpi-detailed-item"><span class="label-main">MH Affectées Vacataires</span><span class="value-main">{{ "%.1f" | format(kpis.get('mh_affectee_vacataires', 0.0)) }}h</span></div>
                <div class="kpi-group-title">Suivi des Heures</div>
                <div class="kpi-item"><span class="label">Proposées (DRIF)</span> <span class="value">{{ "%.1f" | format(kpis.get('mh_proposee_drif_totale', 0.0)) }}h</span></div>
                <div class="kpi-item"><span class="label">Affectées (Total)</span> <span class="value">{{ "%.1f" | format(kpis.get('mh_affectee_totale', 0.0)) }}h</span></div>
                <div class="kpi-item"><span class="label">Réalisées (hors dépassement)</span> <span class="value">{{ "%.1f" | format(kpis.get('mh_realisee_plafonnee_totale', 0.0)) }}h</span></div>
                <div class="kpi-item"><span class="label">Réalisées (dépassement inclu)</span> <span class="value">{{ "%.1f" | format(kpis.get('mh_realisee_brute_totale', 0.0)) }}h</span></div>
                <div class="kpi-group-title">Taux de Réalisation</div>
                <div class="kpi-item"><span class="label">Général (sur Affecté)</span> <span class="value">{{ "%.1f" | format(kpis.get('taux_realisation_general_affecte', 0.0)) }}%</span></div>
                <div class="progress mb-2"><div class="progress-bar" role="progressbar" style="width: {{ kpis.get('taux_realisation_general_affecte', 0.0) }}%;"></div></div>
                <div class="kpi-item"><span class="label">Moyen / Module</span> <span class="value">{{ "%.1f" | format(kpis.get('taux_realisation_moyen_module', 0.0)) }}%</span></div>
                <div class="kpi-group-title">Répartition Semestrielle (Estimée)</div>
                <div class="kpi-item"><span class="label">MH Affectée S1 (Est.)</span> <span class="value">{{ "%.1f" | format(kpis.get('mh_affectee_s1_estimee', 0.0)) }}h</span></div>
                <div class="kpi-item"><span class="label">Taux Réal. S1 (Est.)</span> <span class="value">{{ "%.1f" | format(kpis.get('taux_s1', 0.0)) }}%</span></div>
                <div class="progress mb-2"><div class="progress-bar bg-info" role="progressbar" style="width: {{ kpis.get('taux_s1', 0.0) }}%;"></div></div>
                <div class="kpi-item"><span class="label">MH Affectée S2 (Est.)</span> <span class="value">{{ "%.1f" | format(kpis.get('mh_affectee_s2_estimee', 0.0)) }}h</span></div>
                <div class="kpi-item"><span class="label">Taux Réal. S2 (Est.)</span> <span class="value">{{ "%.1f" | format(kpis.get('taux_s2', 0.0)) }}%</span></div>
                <div class="progress mb-2"><div class="progress-bar bg-info" role="progressbar" style="width: {{ kpis.get('taux_s2', 0.0) }}%;"></div></div>
                <div class="kpi-group-title">Suivi EFM</div>
                <div class="kpi-item"><span class="label">Séances EFM Planifiées</span><span class="value">{{ kpis.get('efm_seances_oui', 0) }} / {{ kpis.get('efm_total_modules_pour_seance', 0) }}</span></div>
                <div class="kpi-detailed-item mt-1"><span class="label-main">Validation EFM (Notes Saisies)</span><span class="value-main">{{ "%.1f" | format(kpis.get('taux_efm_validation', 0.0)) }}%</span><span class="label-sub">{{ kpis.get('efm_validation_oui', 0) }} / {{ kpis.get('efm_total_modules_pour_validation', 0) }} modules validés</span></div>
                <div class="progress mb-2"><div class="progress-bar bg-success" role="progressbar" style="width: {{ kpis.get('taux_efm_validation', 0.0) }}%;"></div></div>
                <div class="mt-auto text-center footer-info pt-3 border-top"><small class="text-muted">Développé par Mehdary Mehdi<br>Dashboard OFPPT v2.14</small></div>
            </nav>
            <button type="button" id="sidebarCollapse" class="btn btn-primary"> <i class="fas fa-bars"></i> </button>
            <div id="main-content">
                <div class="upload-suggestion-bar">
                    <span class="me-auto"></span> <!-- Espaceur pour pousser le bouton suggestion à droite -->
                    <button type="button" class="btn btn-sm btn-info flex-shrink-0" onclick="toggleSuggestionForm()">
                        <i class="fas fa-lightbulb me-1"></i> Donner votre Avis
                    </button>
                </div>
                <!-- Formulaire de suggestion caché -->
                <div id="suggestion-form-container" class="card p-3 mb-3" style="display: {% if request.args.get('show_suggestion_form') == 'true' %}block{% else %}none{% endif %};">
                    <h5 class="card-title">Votre Avis Compte !</h5>
                    <form action="{{ url_for('submit_suggestion') }}" method="post">
                        <div class="mb-2"><label for="nom_suggestion_simple" class="form-label form-label-sm">Nom+etablissement </label>
                            <input type="text" class="form-control form-control-sm" id="nom_suggestion_simple" name="nom_suggestion_simple">
                        </div>
                        <div class="mb-2"><label for="message_suggestion_simple" class="form-label form-label-sm">Message/Suggestion</label>
                            <textarea class="form-control form-control-sm" id="message_suggestion_simple" name="message_suggestion_simple" rows="3" required></textarea>
                        </div>
                        <button type="submit" class="btn btn-sm btn-primary">Envoyer</button>
                        <button type="button" class="btn btn-sm btn-outline-secondary" onclick="toggleSuggestionForm(false)">Annuler</button>
                    </form>
                </div>

                {% with messages = get_flashed_messages(with_categories=true) %} {% if messages %}
                    {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert"> {{ message }} <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button> </div>
                    {% endfor %}
                {% endif %} {% endwith %}
                <header class="page-header"><h1>Tableau de bord de l'avancement des programmes de formation.</h1></header>
                <div class="row"> <div class="col-12 mb-4"><div class="graph-card">{{ graphs.get('avancement_groupe', default_message) | safe }}</div></div> <div class="col-12 mb-4"><div class="graph-card">{{ graphs.get('avancement_formateur', default_message) | safe }}</div></div> <div class="col-12 mb-4"><div class="graph-card">{{ graphs.get('charge_horaire_s1s2_formateur_horizontal', default_message) | safe }}</div></div> </div>
                <div class="row mt-3"><div class="col-12"><div class="graph-card p-3"><h5 class="text-warning mb-3 fw-bold"><i class="fas fa-tasks me-2"></i>Suivi Formateurs: S1 Non Achevés & S2 Entamés(Chaînage pédagogique DRIF)</h5>
                {% if formateurs_s1_nonacheve_s2_entame %}<div class="table-responsive" style="max-height: 300px; overflow-y: auto;"><table class="table table-sm table-hover table-striped small"><thead class="table-light sticky-top"><tr><th>Formateur</th><th>S1 Non Achevés (Groupe/Code Module)</th><th>S2 Entamés (Groupe/Code Module)</th></tr></thead><tbody>
                {% for item in formateurs_s1_nonacheve_s2_entame %}<tr><td>{{ item.nom }}</td>
                <td><span class="badge bg-warning text-dark me-1" title="Nombre">{{ item.nb_s1_non_acheves }}</span> <span title="{{ item.s1_alerte_tooltip }}">{{ item.s1_alerte_display }}</span></td>
                <td><span class="badge bg-info text-dark me-1" title="Nombre">{{ item.nb_s2_entames }}</span> <span title="{{ item.s2_alerte_tooltip }}">{{ item.s2_alerte_display }}</span></td>
                </tr>{% endfor %}</tbody></table></div>
                {% else %}<p class="text-center text-muted fst-italic mt-3">Aucun formateur n'a simultanément des modules S1 non achevés et des modules S2 entamés.</p>{% endif %}
                </div></div></div>
                <div class="row mt-3"><div class="col-12"><div class="graph-card p-3"><h5 class="text-danger mb-3 fw-bold"><i class="fas fa-exclamation-triangle me-2"></i>Formateurs: Notes EFM en Attente (Taux Réalisation Module 100%) </h5>
                {% if formateurs_notes_en_attente %}<div class="table-responsive" style="max-height: 300px; overflow-y: auto;"><table class="table table-sm table-hover table-striped small"><thead class="table-light sticky-top"><tr><th>Formateur</th><th>Code Module</th><th>Groupe</th><th>Taux Réalisation</th></tr></thead><tbody>
                {% for item in formateurs_notes_en_attente %}<tr><td>{{ item.formateur }}</td><td>{{ item.code_module }}</td><td>{{ item.groupe }}</td><td>{{ "%.1f" | format(item.taux_realisation) }}%</td></tr>
                {% endfor %}</tbody></table></div>
                {% else %}<p class="text-center text-muted fst-italic mt-3">Aucune note EFM en attente pour les modules presque terminés.</p>{% endif %}
                </div></div></div>
                <div class="row mt-3"><div class="col-12"><div class="graph-card p-3"><h5 class="text-info mb-3 fw-bold"><i class="fas fa-folder-open me-2"></i>Modules Non Affectés par Secteur(besoin en ressources humaines )</h5>
                {% if modules_non_affectes and modules_non_affectes | length > 0 %}{% for secteur, modules_details_list in modules_non_affectes.items() %}<div class="mb-3"><h6 class="mt-2 mb-1 text-secondary fw-bold">Secteur : {{ secteur }} <span class="badge bg-info rounded-pill ms-2">{{ modules_details_list | length }} module(s)</span></h6><div class="table-responsive" style="max-height: 200px; overflow-y: auto; border-left: 3px solid var(--ofppt-orange); padding-left:10px;"><table class="table table-sm table-borderless mb-0 small"><tbody>
                {% for module_info in modules_details_list %}<tr><td style="width:35%;"><strong class="text-muted">Groupe :</strong> {{ module_info.groupe }}</td><td style="width:65%;"><strong class="text-muted">Module :</strong> {{ module_info.code_module }} {% if module_info.nom_module and module_info.nom_module != module_info.code_module and module_info.nom_module != 'N/A' %} - <span class="text-secondary fst-italic" title="{{ module_info.nom_module_complet }}">{{ module_info.nom_module }}</span>{% endif %}</td></tr>
                {% endfor %}</tbody></table></div></div>{% endfor %}
                {% else %}<p class="text-center text-muted fst-italic mt-3">Tous les modules ont une masse horaire affectée.</p>{% endif %}
                </div></div></div>
                <div class="row mt-4">
                    <div class="col-lg-4 col-md-6 mb-4"><div class="graph-card-small">{{ graphs.get('regional', default_message) | safe }}</div></div>
                    <div class="col-lg-4 col-md-6 mb-4"><div class="graph-card-small">{{ graphs.get('statut_efm', default_message) | safe }}</div></div>
                    <div class="col-lg-4 col-md-12 mb-4"><div class="graph-card-small">{{ graphs.get('repartition_type_formateur', default_message) | safe }}</div></div>
                </div>
            </div>
            <script>
                document.addEventListener('DOMContentLoaded',function(){
                    var sidebar = document.getElementById('sidebar');
                    var sidebarCollapse = document.getElementById('sidebarCollapse');
                    if (sidebarCollapse) {
                        sidebarCollapse.addEventListener('click', function () {
                            sidebar.classList.toggle('active');
                            setTimeout(resizePlotlyCharts, 350); // Resize after sidebar transition
                        });
                    }
                    // Function to show/hide the simple suggestion form
                    window.toggleSuggestionForm = function(show) {
                        var formContainer = document.getElementById('suggestion-form-container');
                        if (typeof show === 'undefined') { // Toggle if no argument
                            formContainer.style.display = formContainer.style.display === 'none' ? 'block' : 'none';
                        } else { // Set display based on argument
                            formContainer.style.display = show ? 'block' : 'none';
                        }
                    }
                    function resizePlotlyCharts(){ document.querySelectorAll('.plotly-graph-div').forEach(function(gd){try{Plotly.Plots.resize(gd)}catch(e){}})}
                    setTimeout(resizePlotlyCharts, 200); 
                    window.addEventListener('resize', resizePlotlyCharts);
                });
            </script>
        </body>
        </html>
        """
        return render_template_string(html_template, kpis=kpis, graphs=graphs, 
                                      formateurs_s1_nonacheve_s2_entame=formateurs_s1_nonacheve_s2_entame_data, 
                                      formateurs_notes_en_attente=formateurs_notes_en_attente_data,
                                      modules_non_affectes=modules_non_affectes_par_secteur,
                                      default_message=default_template_msg)

    except FileNotFoundError as e_fnf: app.logger.error(f"Fichier non trouvé: {e_fnf}", exc_info=True); return render_template_string(f"""<!DOCTYPE html><html>...HTML Erreur Fichier Non Trouvé...</html>""", default_message=default_template_msg)
    except Exception as e_global: app.logger.error(f"Erreur globale: {e_global}", exc_info=True); return render_template_string(f"""<!DOCTYPE html><html>...HTML Erreur Globale...</html>""", default_message=default_template_msg)

# --- Démarrage de l'application ---
if __name__ == '__main__':
    data_dir = os.path.join(BASE_DIR, "data")
    if not os.path.exists(data_dir):
        try: os.makedirs(data_dir); app.logger.info(f"Dossier '{data_dir}' créé.")
        except OSError as e: app.logger.error(f"Impossible de créer dossier '{data_dir}': {e}")
    
    # Décommenter et adapter pour créer un fichier de test
    # try:
    #     dummy_data_v14_txt = {
    #         'Groupe': ['DEV101', 'DEV101', 'TSI201', 'GEB301', 'DEV102', 'TSI201', 'AGR001', 'DEV101'],
    #         'Formateur Affecté Présentiel Actif': ['Durand Paul', 'Durand Paul', 'Bernard Luc', 'Petit Lea', 'Martin Sophie', 'Bernard Luc', 'Fermier Jean', 'Durand Paul'],
    #         'Mle Affecté Présentiel Actif': ['P12345', 'P12345', 'P54321', 'CD12345', 'AB67890', 'P54321', 'AZ98765', 'P12345'],
    #         'Effectif Groupe': [20, 20, 18, 25, 20, 18, 30, 20],
    #         'MH Totale DRIF': [100, 120, 90, 110, 80, 95, 70, 60], 
    #         'Régional': ['O', 'N', 'O', 'N', 'O', 'N', 'O', 'N'],
    #         'Secteur': ['Tertiaire', 'Tertiaire', 'Industrie', 'BTP', 'Tertiaire', 'Industrie', 'Agriculture', 'Tertiaire'], 
    #         'filière': ['Développement Web', 'Développement Web', 'Réseaux', 'Génie Civil', 'Développement Mobile', 'Réseaux', 'Agronomie', 'Développement Web'],
    #         'Module': ['HTML S1', 'CSS S1', 'Firewall S1', 'Topographie S2', 'Kotlin S2', 'Ethical Hacking S2', 'Botanique S1', 'PHP S2'], 
    #         'Code Module': ['M01HTML', 'M01CSS', 'M03FIRE', 'M04TOPO', 'M02KOTL', 'M06ETHICK', 'AGR_B01', 'M07PHP'],
    #         'Type de formation': ['D', 'D', 'Q', 'D', 'D', 'Q', 'D', 'D'],
    #         'Séance EFM': ['Oui', 'Oui', 'Non', 'Oui', 'Oui', 'Oui', 'Non', 'Oui'],
    #         'Validation EFM': ['Oui', 'Non', 'Non défini', 'Oui', 'Non renseigné', 'Non', 'Non défini', 'Non'],
    #         'MH Affectée Globale (P & SYN)': [40, 50, 80, 100, 70, 85, 0.05, 60], 
    #         'MH Réalisée Globale':    [30, 40, 80, 98, 69, 84, 0, 10],
    #         'MH Totale S1 DRIF':      [40, 50, 80, 0,  0,  0, 70, 0], 
    #         'MH Totale S2 DRIF':      [0,  0,  0, 100, 70, 85, 0, 60],
    #     }
    #     dummy_df = pd.DataFrame(dummy_data_v14_txt)
    #     dummy_filename = os.path.join(data_dir, "AvancementProgramme_SimpleSugg.xlsx")
    #     if os.path.exists(data_dir):
    #        dummy_df.to_excel(dummy_filename, index=False, sheet_name="AvancementProgramme")
    #        app.logger.info(f"Fichier Excel de test '{dummy_filename}' créé.")
    # except Exception as e_dummy: app.logger.error(f"Erreur création fichier dummy: {e_dummy}", exc_info=True)

    app.run(host='0.0.0.0', port=5000, debug=True)
