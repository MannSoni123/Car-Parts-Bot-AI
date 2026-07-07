from flask import Blueprint, jsonify, request
from sqlalchemy import or_, and_
from ..extensions import db


search_bp = Blueprint("search", __name__)

