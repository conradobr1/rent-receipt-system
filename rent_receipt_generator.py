from tkinter import *
from tkinter import ttk, messagebox
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdf_canvas
from datetime import datetime
from PIL import Image, ImageDraw, ImageTk
import json
import os
import hashlib
import uuid
import qrcode
import base64
from io import BytesIO
import subprocess
import platform

# ---------------- ORGANIZED FOLDERS ----------------
BASE_FOLDER = "sistema_recibos"
DATA_FOLDER = os.path.join(BASE_FOLDER, "dados")
PDF_FOLDER = os.path.join(BASE_FOLDER, "pdfs")
BLOCKCHAIN_FOLDER = os.path.join(BASE_FOLDER, "blockchain")
TENANTS_FOLDER = os.path.join(BASE_FOLDER, "locatarios")
SIGNATURE_FOLDER = os.path.join(BASE_FOLDER, "assinaturas")

# Files inside folders
BLOCKCHAIN_FILE = os.path.join(BLOCKCHAIN_FOLDER, "blockchain.json")
TENANTS_FILE = os.path.join(TENANTS_FOLDER, "locatarios.json")
SIGNATURE_FILE = os.path.join(SIGNATURE_FOLDER, "assinatura.png")

# Create folders if they don't exist
for folder in [BASE_FOLDER, DATA_FOLDER, PDF_FOLDER, BLOCKCHAIN_FOLDER, 
               TENANTS_FOLDER, SIGNATURE_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# ---------------- SIMULATED BLOCKCHAIN ----------------
class ReceiptBlockchain:
    def __init__(self):
        self.chain_file = BLOCKCHAIN_FILE
        self.chain = self.load_chain()
        
    def load_chain(self):
        """Loads blockchain from file"""
        if os.path.exists(self.chain_file):
            with open(self.chain_file, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            # Genesis block (first block)
            genesis_block = {
                "index": 0,
                "timestamp": str(datetime.now()),
                "data": "Genesis Block",
                "previous_hash": "0",
                "hash": self.calculate_hash(0, "Genesis Block", "0", str(datetime.now())),
                "receipt_id": "GENESIS-0000"
            }
            return [genesis_block]
    
    def calculate_hash(self, index, data, previous_hash, timestamp):
        """Calculates SHA-256 hash of the block"""
        block_string = f"{index}{data}{previous_hash}{timestamp}"
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    def create_receipt_block(self, receipt_data):
        """Creates a new block for the receipt"""
        previous_block = self.chain[-1]
        index = len(self.chain)
        
        # Generates unique receipt ID
        receipt_id = f"REC-{uuid.uuid4().hex[:8].upper()}-{datetime.now().strftime('%Y%m%d')}"
        
        # Block data (WITHOUT landlord's CPF)
        block_data = {
            "receipt_id": receipt_id,
            "landlord": receipt_data.get("landlord"),
            "tenant": receipt_data.get("tenant"),
            "tenant_cpf": receipt_data.get("tenant_cpf"),
            "value": receipt_data.get("value"),
            "reference": receipt_data.get("reference"),
            "day": receipt_data.get("day"),
            "address": receipt_data.get("address"),
            "timestamp": str(datetime.now())
        }
        
        # Creates the block
        new_block = {
            "index": index,
            "timestamp": str(datetime.now()),
            "data": block_data,
            "previous_hash": previous_block["hash"],
            "hash": self.calculate_hash(index, json.dumps(block_data), previous_block["hash"], str(datetime.now())),
            "receipt_id": receipt_id
        }
        
        # Adds to the chain
        self.chain.append(new_block)
        self.save_chain()
        
        return receipt_id, new_block["hash"]
    
    def save_chain(self):
        """Saves chain to file"""
        with open(self.chain_file, "w", encoding="utf-8") as f:
            json.dump(self.chain, f, indent=4, ensure_ascii=False)
    
    def verify_receipt(self, receipt_id):
        """Verifies receipt authenticity"""
        for block in self.chain:
            if block.get("receipt_id") == receipt_id:
                # Verifies hash
                calculated_hash = self.calculate_hash(
                    block["index"],
                    json.dumps(block["data"]),
                    block["previous_hash"],
                    block["timestamp"]
                )
                return calculated_hash == block["hash"], block
        return False, None
    
    def get_receipt_info(self, receipt_id):
        """Gets receipt information by ID"""
        for block in self.chain:
            if block.get("receipt_id") == receipt_id:
                return block["data"]
        return None

# Initialize blockchain
blockchain = ReceiptBlockchain()

# ---------------- DATA STORAGE ----------------
tenants = []

def load_tenants():
    global tenants
    if os.path.exists(TENANTS_FILE):
        with open(TENANTS_FILE, "r", encoding="utf-8") as f:
            tenants = json.load(f)
            tenant_combo["values"] = [t["name"] for t in tenants]

def save_tenants():
    with open(TENANTS_FILE, "w", encoding="utf-8") as f:
        json.dump(tenants, f, indent=4, ensure_ascii=False)

# ---------------- SIGNATURE (FIXED + SAVED) ----------------
signature_points = []
drawing = False

def start_signature(event):
    global drawing
    drawing = True
    signature_points.clear()
    signature_points.append((event.x, event.y))

def draw_signature(event):
    if not drawing or not signature_points:
        return
    x, y = event.x, event.y
    last_x, last_y = signature_points[-1]
    canvas_signature.create_line(
        last_x, last_y, x, y,
        width=2, capstyle=ROUND, smooth=True
    )
    signature_points.append((x, y))

def stop_signature(event):
    global drawing
    drawing = False

def clear_signature():
    canvas_signature.delete("all")
    signature_points.clear()

def save_signature():
    if not signature_points:
        messagebox.showerror("Error", "No signature to save.")
        return

    img = Image.new("RGB", (400, 150), "white")
    draw = ImageDraw.Draw(img)

    for i in range(1, len(signature_points)):
        draw.line(
            [signature_points[i-1], signature_points[i]],
            fill="black",
            width=2
        )

    img.save(SIGNATURE_FILE)
    messagebox.showinfo("Success", "Signature saved successfully!")

def load_saved_signature():
    if not os.path.exists(SIGNATURE_FILE):
        messagebox.showerror("Error", "No saved signature found.")
        return

    img = Image.open(SIGNATURE_FILE)
    img_tk = ImageTk.PhotoImage(img)

    canvas_signature.delete("all")
    canvas_signature.image = img_tk
    canvas_signature.create_image(0, 0, anchor=NW, image=img_tk)

# ---------------- FUNÇÃO PARA ABRIR PASTA PDF ----------------
def open_pdf_folder():
    """Abre a pasta PDF no explorador de arquivos do sistema"""
    try:
        pdf_path = os.path.abspath(PDF_FOLDER)
        
        # Verifica se a pasta existe
        if not os.path.exists(pdf_path):
            messagebox.showwarning("Aviso", f"A pasta PDF não existe:\n{pdf_path}")
            return
        
        # Abre a pasta no explorador de arquivos de acordo com o sistema operacional
        system = platform.system()
        
        if system == "Windows":
            os.startfile(pdf_path)
        elif system == "Darwin":  # macOS
            subprocess.run(["open", pdf_path])
        else:  # Linux e outros
            subprocess.run(["xdg-open", pdf_path])
            
    except Exception as e:
        messagebox.showerror("Erro", f"Não foi possível abrir a pasta:\n{str(e)}")

# ---------------- TENANT REGISTRATION ----------------
def save_tenant():
    name = entry_tenant_name.get()
    cpf = entry_tenant_cpf.get()
    address = entry_tenant_address.get()

    if not all([name, cpf, address]):
        messagebox.showerror("Error", "Fill in all fields.")
        return

    tenants.append({
        "name": name,
        "cpf": cpf,
        "address": address
    })

    save_tenants()
    tenant_combo["values"] = [t["name"] for t in tenants]

    entry_tenant_name.delete(0, END)
    entry_tenant_cpf.delete(0, END)
    entry_tenant_address.delete(0, END)

    messagebox.showinfo("Success", "Tenant registered and saved!")

# ---------------- SCREEN NAVIGATION ----------------
def show_register():
    frame_receipt.pack_forget()
    frame_verify.pack_forget()
    frame_register.pack(fill="both", expand=True)

def show_receipt():
    if not tenants:
        messagebox.showerror("Error", "Register at least one tenant.")
        return
    frame_register.pack_forget()
    frame_verify.pack_forget()
    frame_receipt.pack(fill="both", expand=True)

def show_verify():
    frame_receipt.pack_forget()
    frame_register.pack_forget()
    frame_verify.pack(fill="both", expand=True)

# ---------------- AUTO FILL ----------------
def fill_tenant_data(event):
    selected = tenant_combo.get()
    for t in tenants:
        if t["name"] == selected:
            label_cpf_value.config(text=t["cpf"])
            label_address_value.config(text=t["address"])
            break

# ---------------- QR CODE GENERATOR ----------------
def generate_qr_code(data):
    """Generates QR Code with receipt data and returns as Image object"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=6,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    return img

# ---------------- PDF WITH BLOCKCHAIN ----------------
def generate_receipt():
    if not os.path.exists(SIGNATURE_FILE):
        messagebox.showerror("Error", "Save or load a signature.")
        return

    landlord = entry_landlord.get()
    tenant_name = tenant_combo.get()
    value = entry_value.get()
    reference = entry_reference.get()
    day = entry_day.get()

    if not all([landlord, tenant_name, value, reference, day]):
        messagebox.showerror("Error", "Fill in all fields.")
        return

    tenant = next(t for t in tenants if t["name"] == tenant_name)

    # Registers in blockchain
    receipt_data = {
        "landlord": landlord,
        "tenant": tenant["name"],
        "tenant_cpf": tenant["cpf"],
        "value": value,
        "reference": reference,
        "day": day,
        "address": tenant["address"]
    }
    
    # Generates unique ID and hash in blockchain
    receipt_id, block_hash = blockchain.create_receipt_block(receipt_data)
    
    # PDF file name
    pdf_filename = f"recibo_{receipt_id}.pdf"
    pdf_path = os.path.join(PDF_FOLDER, pdf_filename)

    pdf = pdf_canvas.Canvas(pdf_path, pagesize=A4)

    w, h = A4
    
    # Title
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(200, h - 80, "RECIBO DE ALUGUEL")
    
    # Unique Receipt ID
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(50, h - 105, f"ID ÚNICO: {receipt_id}")
    
    # Separator line
    pdf.line(50, h - 115, w - 50, h - 115)
    
    # Receipt body
    pdf.setFont("Helvetica", 12)
    start_y = h - 145
    
    # Receipt text
    pdf.drawString(50, start_y, f"Recebi de {tenant['name']}, CPF/CNPJ {tenant['cpf']},")
    pdf.drawString(50, start_y - 25, f"a quantia de R$ {value}, referente ao aluguel")
    pdf.drawString(50, start_y - 50, f"do imóvel localizado em {tenant['address']}.")
    
    # Space
    pdf.drawString(50, start_y - 90, f"Referente ao dia {day}/{reference}")
    pdf.drawString(50, start_y - 115, f"Data de emissão: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    # Landlord (WITHOUT CPF)
    pdf.drawString(50, start_y - 160, "________________________________________________________________")
    pdf.drawString(50, start_y - 185, f"Locador: {landlord}")
    
    # SIGNATURE
    signature_x = 150
    text_y = start_y - 300
    
    # "Assinatura:" text on the left
    pdf.drawString(50, text_y, "Assinatura:")
    
    # Signature image on the right
    if os.path.exists(SIGNATURE_FILE):
        pdf.drawImage(
            SIGNATURE_FILE,
            signature_x,
            text_y - 10,
            width=180,
            height=60,
            preserveAspectRatio=True,
            mask='auto'
        )
    
    # Line for signature
    pdf.line(50, text_y - 5, w - 50, text_y - 5)
    
    # Small QR Code in footer
    security_y = 100  # Fixed position in footer
    
    # Generates verification QR Code in memory
    qr_data = f"RECIBO|ID:{receipt_id}|HASH:{block_hash[:15]}"
    qr_img = generate_qr_code(qr_data)
    
    # Saves QR Code temporarily for use in PDF
    temp_qr_path = os.path.join(DATA_FOLDER, f"temp_qr_{receipt_id}.png")
    qr_img.save(temp_qr_path)
    
    # Adds small QR Code in footer
    pdf.drawImage(
        temp_qr_path,
        w - 100,  # Bottom right corner
        30,       # Close to bottom edge
        width=50,
        height=50,
        preserveAspectRatio=True,
        mask='auto'
    )
    
    # Small security text in footer
    pdf.setFont("Helvetica", 7)
    pdf.drawString(50, 40, f"ID: {receipt_id} | Hash: {block_hash[:12]}... | Verificação: Sistema de Recibos")
    
    pdf.showPage()
    pdf.save()
    
    # Remove temporary QR code
    if os.path.exists(temp_qr_path):
        os.remove(temp_qr_path)

    messagebox.showinfo("Success", 
                       f"✅ Recibo gerado com sucesso!\n\n"
                       f"📄 ID Único: {receipt_id}\n"
                       f"💾 Salvo em: {pdf_path}")
    
    # Clear fields after generation
    entry_landlord.delete(0, END)
    entry_value.delete(0, END)
    entry_day.delete(0, END)
    entry_reference.delete(0, END)

# ---------------- RECEIPT VERIFICATION ----------------
def verify_receipt():
    receipt_id = entry_verify_id.get().strip()
    
    if not receipt_id:
        messagebox.showerror("Error", "Enter receipt ID to verify.")
        return
    
    # Verifies in blockchain
    is_valid, block_data = blockchain.verify_receipt(receipt_id)
    
    if is_valid:
        # Gets receipt information
        receipt_info = blockchain.get_receipt_info(receipt_id)
        
        if receipt_info:
            # Shows information
            info_text = (
                f"✅ RECIBO AUTÊNTICO E VÁLIDO\n\n"
                f"📋 ID: {receipt_id}\n"
                f"🔒 Hash: {block_data['hash'][:25]}...\n"
                f"📅 Emitido em: {receipt_info['timestamp'][:19]}\n\n"
                f"👤 Locador: {receipt_info['landlord']}\n"
                f"👥 Locatário: {receipt_info['tenant']}\n"
                f"📝 CPF Locatário: {receipt_info['tenant_cpf']}\n"
                f"💰 Valor: R$ {receipt_info['value']}\n"
                f"📅 Referência: {receipt_info['reference']}\n"
                f"📆 Dia: {receipt_info['day']}\n"
                f"📍 Endereço: {receipt_info.get('address', 'Não informado')[:40]}...\n\n"
                f"🔗 Bloco #{block_data['index']} na blockchain"
            )
            
            label_verify_result.config(
                text=info_text,
                fg="green",
                font=("Arial", 9)
            )
        else:
            label_verify_result.config(
                text="❌ Erro ao obter informações do recibo.",
                fg="red"
            )
    else:
        label_verify_result.config(
            text="❌ RECIBO INVÁLIDO OU FALSIFICADO!\n\n"
                 "Este ID não existe na blockchain ou foi adulterado.",
            fg="red",
            font=("Arial", 9, "bold")
        )

# Statistics button
def show_blockchain_stats():
    total_receipts = len(blockchain.chain) - 1  # Excludes genesis block
    messagebox.showinfo("Estatísticas do Sistema", 
                       f"📊 SISTEMA DE RECIBOS\n\n"
                       f"📈 Total de Recibos: {total_receipts}\n"
                       f"📂 Pasta principal: {os.path.abspath(BASE_FOLDER)}\n"
                       f"📄 PDFs: {PDF_FOLDER}\n"
                       f"🔗 Blockchain: {BLOCKCHAIN_FOLDER}\n"
                       f"👥 Locatários: {TENANTS_FOLDER}")

# ---------------- GUI ----------------
window = Tk()
window.title("Sistema de Recibos")
window.geometry("700x850")
window.resizable(False, False)

# ---------------- MENU ----------------
menu = Frame(window, bg="#f0f0f0", height=40)
menu.pack(fill="x")

Button(menu, text="Cadastro de Locatários", command=show_register, bg="#2196F3", fg="white", width=18).pack(side=LEFT, padx=3, pady=5)
Button(menu, text="Gerar Recibo", command=show_receipt, bg="#4CAF50", fg="white", width=18).pack(side=LEFT, padx=3, pady=5)
Button(menu, text="Verificar Recibo", command=show_verify, bg="#FF9800", fg="white", width=18).pack(side=LEFT, padx=3, pady=5)
Button(menu, text="📁 Pasta PDF", command=open_pdf_folder, bg="#9C27B0", fg="white", width=15).pack(side=LEFT, padx=3, pady=5)

# ---------------- REGISTER SCREEN ----------------
frame_register = Frame(window)

Label(frame_register, text="Cadastro de Locatário", font=("Arial", 16, "bold")).pack(pady=15)

Label(frame_register, text="Nome do Locatário:").pack(anchor="w", padx=50)
entry_tenant_name = Entry(frame_register, width=65, font=("Arial", 10))
entry_tenant_name.pack(pady=2)

Label(frame_register, text="CPF/CNPJ:").pack(anchor="w", padx=50)
entry_tenant_cpf = Entry(frame_register, width=65, font=("Arial", 10))
entry_tenant_cpf.pack(pady=2)

Label(frame_register, text="Endereço Completo:").pack(anchor="w", padx=50)
entry_tenant_address = Entry(frame_register, width=65, font=("Arial", 10))
entry_tenant_address.pack(pady=2)

Button(
    frame_register,
    text="Salvar Locatário",
    command=save_tenant,
    bg="#1976D2",
    fg="white",
    font=("Arial", 10, "bold"),
    height=2,
    width=25
).pack(pady=25)

# ---------------- RECEIPT SCREEN ----------------
frame_receipt = Frame(window)

Label(frame_receipt, text="Gerar Recibo de Aluguel", font=("Arial", 16, "bold")).pack(pady=15)

Label(frame_receipt, text="Nome do Locador:").pack(anchor="w", padx=50)
entry_landlord = Entry(frame_receipt, width=65, font=("Arial", 10))
entry_landlord.pack(pady=2)

Label(frame_receipt, text="Locatário:").pack(anchor="w", padx=50)
tenant_combo = ttk.Combobox(frame_receipt, state="readonly", width=62, font=("Arial", 10))
tenant_combo.pack(pady=2)
tenant_combo.bind("<<ComboboxSelected>>", fill_tenant_data)

Label(frame_receipt, text="CPF/CNPJ:").pack(anchor="w", padx=50)
label_cpf_value = Label(frame_receipt, text="-", font=("Arial", 10), fg="#666")
label_cpf_value.pack(pady=2)

Label(frame_receipt, text="Endereço do Imóvel:").pack(anchor="w", padx=50)
label_address_value = Label(frame_receipt, text="-", wraplength=550, font=("Arial", 10), fg="#666")
label_address_value.pack(pady=2)

Label(frame_receipt, text="Valor do Aluguel (R$):").pack(anchor="w", padx=50)
entry_value = Entry(frame_receipt, width=65, font=("Arial", 10))
entry_value.pack(pady=2)

frame_dates = Frame(frame_receipt)
frame_dates.pack(pady=10)
Label(frame_dates, text="Dia do Pagamento:").pack(side=LEFT, padx=5)
entry_day = Entry(frame_dates, width=10, font=("Arial", 10))
entry_day.pack(side=LEFT, padx=5)
Label(frame_dates, text="Mês/Ano (MM/AAAA):").pack(side=LEFT, padx=5)
entry_reference = Entry(frame_dates, width=15, font=("Arial", 10))
entry_reference.pack(side=LEFT, padx=5)

Label(frame_receipt, text="Assinatura (use o mouse):", font=("Arial", 10, "bold")).pack(pady=10)
canvas_signature = Canvas(frame_receipt, width=400, height=150, bg="white", bd=2, relief="solid")
canvas_signature.pack()

canvas_signature.bind("<Button-1>", start_signature)
canvas_signature.bind("<B1-Motion>", draw_signature)
canvas_signature.bind("<ButtonRelease-1>", stop_signature)

frame_signature_buttons = Frame(frame_receipt)
frame_signature_buttons.pack(pady=5)
Button(frame_signature_buttons, text="Limpar Assinatura", command=clear_signature, width=18).pack(side=LEFT, padx=2)
Button(frame_signature_buttons, text="Salvar assinatura padrão", command=save_signature, width=18).pack(side=LEFT, padx=2)
Button(frame_signature_buttons, text="Usar assinatura salva", command=load_saved_signature, width=18).pack(side=LEFT, padx=2)

Button(
    frame_receipt,
    text="Gerar Recibo",
    command=generate_receipt,
    bg="#2E7D32",
    fg="white",
    font=("Arial", 11, "bold"),
    height=2,
    width=30
).pack(pady=15)

# Botão para abrir pasta PDF na tela de recibos
Button(
    frame_receipt,
    text="📁 Abrir Pasta de PDFs",
    command=open_pdf_folder,
    bg="#9C27B0",
    fg="white",
    font=("Arial", 10, "bold"),
    height=1,
    width=25
).pack(pady=10)

# ---------------- VERIFICATION SCREEN ----------------
frame_verify = Frame(window)

Label(frame_verify, text="Verificar Recibo", font=("Arial", 16, "bold")).pack(pady=15)

Label(frame_verify, text="Digite o ID Único do Recibo:", font=("Arial", 11)).pack(pady=5)
entry_verify_id = Entry(frame_verify, width=65, font=("Arial", 12))
entry_verify_id.pack(pady=10)

Button(
    frame_verify,
    text="Verificar Recibo",
    command=verify_receipt,
    bg="#FF9800",
    fg="white",
    font=("Arial", 11, "bold"),
    height=2,
    width=25
).pack(pady=20)

# Result frame
result_frame = Frame(frame_verify, bg="#f9f9f9", bd=2, relief="solid")
result_frame.pack(pady=10, padx=20, fill="both", expand=True)

label_verify_result = Label(result_frame, text="", justify=LEFT, wraplength=600, 
                           font=("Arial", 10), bg="#f9f9f9", padx=10, pady=10)
label_verify_result.pack(pady=10)

# Statistics button
Button(
    frame_verify,
    text="Ver Estatísticas do Sistema",
    command=show_blockchain_stats,
    bg="#2196F3",
    fg="white",
    font=("Arial", 10),
    height=1,
    width=30
).pack(pady=10)

# Botão para abrir pasta PDF na tela de verificação
Button(
    frame_verify,
    text="📁 Abrir Pasta de PDFs",
    command=open_pdf_folder,
    bg="#9C27B0",
    fg="white",
    font=("Arial", 10),
    height=1,
    width=25
).pack(pady=10)

# ---------------- START ----------------
load_tenants()
show_receipt()
window.mainloop()