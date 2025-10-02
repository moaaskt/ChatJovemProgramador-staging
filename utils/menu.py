class Menu:
    @staticmethod
    def mostrar():
        print("\n📋 **MENU PRINCIPAL**")
        print("1. Sobre o programa")
        print("2. Dúvidas frequentes")
        print("3. Cidades participantes")
        print("4. Chat livre")
        print("5. Sair")
        return input("Escolha uma opção: ")
    
    @staticmethod
    def exibir_duvidas(dados):
        print("\n🔍 **DÚVIDAS FREQUENTES**")
        for i, pergunta in enumerate(dados["duvidas"].keys(), 1):
            print(f"{i}. {pergunta}")
        escolha = input("\nDigite o número da dúvida ou 'voltar': ")
        
        if escolha.lower() == 'voltar':
            return
        try:
            escolha = int(escolha) - 1
            print("\n💡 Resposta:", list(dados["duvidas"].values())[escolha])
        except (ValueError, IndexError):
            print("❌ Opção inválida. Tente novamente.")