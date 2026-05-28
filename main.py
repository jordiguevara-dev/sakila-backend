import os
import uvicorn
from fastapi import FastAPI
from supabase import create_client
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

app = FastAPI()

# Modelos de Datos Pydantic para validar entradas
class Rental(BaseModel):
    inventory_id: int
    customer_id: int
    staff_id: int

class Payment(BaseModel):
    rental_id: int
    amount: float

class CustomerInput(BaseModel):
    store_id: int
    first_name: str
    last_name: str
    email: str

@app.get("/")
def inicio():
    return {"status": "Servidor Sakila en la Nube Operativo"}

# 1. VER INVENTARIO COMPLETO CON NOMBRES Y PRECIOS REALES
@app.get("/inventory")
def listar_inventario():
    # Jalamos el catálogo con el join de film para traer título y tarifa real
    query = supabase.table("inventory").select("inventory_id, available, store_id, film(title, rental_rate)").execute()
    
    # Formateamos la respuesta en un JSON plano para que Java lo lea súper fácil sin romperse
    lista_plana = []
    for item in query.data:
        lista_plana.append({
            "inventory_id": str(item["inventory_id"]),
            "available": str(item["available"]).lower(),
            "store_id": str(item["store_id"]),
            "title": str(item["film"]["title"]).upper() if item["film"] else "PELÍCULA DESCONOCIDA",
            "rental_rate": str(item["film"]["rental_rate"]) if item["film"] else "2.99"
        })
    return lista_plana

# 2. VER TODOS LOS CLIENTES DE SUPABASE EN TIEMPO REAL
@app.get("/customers")
def listar_clientes():
    query = supabase.table("customer").select("customer_id, first_name, last_name, email, active").execute()
    lista_clientes = []
    for c in query.data:
        lista_clientes.append({
            "customer_id": str(c["customer_id"]),
            "first_name": str(c["first_name"]),
            "last_name": str(c["last_name"]),
            "email": str(c["email"]),
            "active": str(c["active"]).lower()
        })
    return lista_clientes

# 3. REGISTRAR UN NUEVO ALQUILER REAL
@app.post("/rentals")
def crear_alquiler(rental: Rental):
    # Validar inventario existente
    inventario = supabase.table("inventory").select("inventory_id, available, film(title)").eq("inventory_id", rental.inventory_id).execute()
    if not inventario.data:
        return {"error": "El ID de inventario no existe"}
    
    inv_data = inventario.data[0]
    if inv_data["available"] == False:
        return {"error": f"La película '{inv_data['film']['title']}' NO está disponible"}

    # Registrar el alquiler en la tabla rental de Supabase
    nuevo = supabase.table("rental").insert({
        "inventory_id": rental.inventory_id,
        "customer_id": rental.customer_id,
        "staff_id": rental.staff_id
    }).execute()

    # Cambiar estado físico en inventario a NO disponible (false)
    supabase.table("inventory").update({"available": False}).eq("inventory_id", rental.inventory_id).execute()

    return {"mensaje": "Alquiler procesado exitosamente"}

# 4. PROCESAR UNA DEVOLUCIÓN MEDIANTE EL ID DEL ALQUILER (RENTAL ID)
@app.put("/returns/{rental_id}")
def devolver_pelicula(rental_id: int):
    rental = supabase.table("rental").select("inventory_id").eq("rental_id", rental_id).execute()
    if not rental.data:
        return {"error": "ID de alquiler no encontrado"}
    
    inv_id = rental.data[0]["inventory_id"]

    # Liberar el inventario (disponible = true)
    supabase.table("inventory").update({"available": True}).eq("inventory_id", inv_id).execute()
    return {"mensaje": "La película ha sido devuelta y liberada con éxito"}

# 5. REGISTRAR PAGO REAL EN LA TABLA PAYMENT
@app.post("/payments")
def crear_pago(payment: Payment):
    # Buscar a qué cliente le corresponde ese alquiler para guardar su historial
    rental = supabase.table("rental").select("customer_id, staff_id").eq("rental_id", payment.rental_id).execute()
    if not rental.data:
        return {"error": "El ID de alquiler no registra transacciones"}
    
    c_id = rental.data[0]["customer_id"]
    s_id = rental.data[0]["staff_id"]

    # Insertar en la tabla payment
    supabase.table("payment").insert({
        "customer_id": c_id,
        "staff_id": s_id,
        "rental_id": payment.rental_id,
        "amount": payment.amount
    }).execute()

    return {"mensaje": "Pago registrado en caja"}

# 6. AGREGAR CLIENTE DIRECTAMENTE EN SUPABASE DESDE JAVA
@app.post("/customers")
def agregar_cliente(customer: CustomerInput):
    supabase.table("customer").insert({
        "store_id": customer.store_id,
        "first_name": customer.first_name,
        "last_name": customer.last_name,
        "email": customer.email,
        "active": True
    }).execute()
    return {"mensaje": "Cliente creado con éxito"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)