@echo off
echo ==========================================
echo   Atualizando o codigo no GitHub...
echo ==========================================

git add .
git commit -m "Atualizando arquivos do bot"
git pull origin main --rebase
git push origin main

echo.
echo ==========================================
echo Pronto! GitHub sincronizado e atualizado!
echo ==========================================
pause