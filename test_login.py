import requests
import time
import json

print("Aguardando servidor inicializar...")
time.sleep(5)

print("\n=== TESTE DE LOGIN ===")
print("Enviando POST /admin/api/login")
print("Payload: {'username': 'admin', 'password': 'admin123'}")

try:
    response = requests.post(
        'http://localhost:5000/admin/api/login',
        json={'username': 'admin', 'password': 'admin123'},
        timeout=10
    )
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    
    try:
        data = response.json()
        print(f"Response JSON: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if data.get('ok') or data.get('success'):
            print("\n✅ LOGIN BEM-SUCEDIDO!")
        else:
            print("\n❌ LOGIN FALHOU!")
            print(f"Motivo: {data.get('message', 'Desconhecido')}")
    except:
        print(f"Response Text: {response.text}")
        
except requests.exceptions.ConnectionError:
    print("\n❌ ERRO: Não foi possível conectar ao servidor.")
    print("Verifique se o servidor está rodando na porta 5000.")
except Exception as e:
    print(f"\n❌ ERRO: {e}")

