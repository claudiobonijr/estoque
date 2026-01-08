@echo off
title Abrindo Sistema de Estoque
python -m streamlit run compras.py --server.address 0.0.0.0 --server.port 8501 --server.enableCORS false --server.enableXsrfProtection false
pause