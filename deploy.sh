#!/bin/bash

echo "Preparing for deployment..."
echo "1. Checking dependencies..."

# Check if required files exist
if [ ! -f "requirements.txt" ]; then
    echo "Error: requirements.txt not found!"
    exit 1
fi

if [ ! -f "app.py" ]; then
    echo "Error: app.py not found!"
    exit 1
fi

echo "2. Creating production requirements..."
pip freeze > requirements.txt

echo "3. Testing application..."
python app.py &
APP_PID=$!
sleep 5

if ps -p $APP_PID > /dev/null; then
    echo "Application test successful!"
    kill $APP_PID
else
    echo "Error: Application failed to start!"
    exit 1
fi

echo "4. Deployment ready!"
echo "Next steps:"
echo "1. git add ."
echo "2. git commit -m 'Deployment ready'"
echo "3. git push"
echo "4. Deploy on Render.com"