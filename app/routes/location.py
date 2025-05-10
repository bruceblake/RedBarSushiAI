# app/routes/location.py

import json
import logging
import requests
from flask import Blueprint, request, session, jsonify, Response
from twilio.twiml.voice_response import VoiceResponse
from app.config import settings