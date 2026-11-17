from flask import Blueprint, render_template, jsonify
from modules.auth import login_required
from database import (
    get_dashboard_metrics,
    get_income_vs_expenses_chart_data,
    get_crop_production_chart_data,
    get_livestock_breakdown
)

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    metrics = get_dashboard_metrics()
    return render_template('dashboard/index.html', metrics=metrics)

# API Endpoints for Chart.js
@dashboard_bp.route('/api/charts/income-expenses')
@login_required
def api_income_expenses():
    data = get_income_vs_expenses_chart_data(months=6)
    return jsonify(data)

@dashboard_bp.route('/api/charts/crop-production')
@login_required
def api_crop_production():
    data = get_crop_production_chart_data()
    return jsonify(data)

@dashboard_bp.route('/api/charts/livestock-breakdown')
@login_required
def api_livestock_breakdown():
    data = get_livestock_breakdown()
    return jsonify(data)
