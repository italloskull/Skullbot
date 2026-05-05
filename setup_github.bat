@echo off
echo ==========================================
echo   Automatizador de Envio para o GitHub
echo ==========================================
set repo_url=https://github.com/italloskull/Skullbot.git

if "%repo_url%"=="" (
    echo Erro: Voce precisa informar o link! Cancelando...
    pause
    exit /b
)

echo.
echo [1/6] Inicializando o Git...
git init

echo [2/6] Adicionando os arquivos...
git add .

echo [3/6] Criando o commit...
git commit -m "Primeiro commit do bot do Online-Fix"

echo [4/6] Configurando a branch principal...
git branch -M main

echo [5/6] Conectando com o GitHub...
git remote add origin %repo_url%

echo [6/6] Enviando os arquivos para a nuvem...
git push -u origin main

echo.
echo ==========================================
echo Pronto! Arquivos enviados com sucesso!
echo ==========================================
pause
