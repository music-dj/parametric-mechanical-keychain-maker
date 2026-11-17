// Creado por Alberto Nicas (Marzo de 2024)
// Cadena Llavero Personalizado con Texto v1.0

/* [General] */
// Texto a representar
texto = "ALBERTO";

// Selector de fuente
fuente_seleccionada = "Bungee"; // [Archivo Black, Bangers, Bungee, Changa One, Bebas Neue, Poppins Black, Sedgwick Ave Display]

// Tamaño de la letra
tamano_letra = 10;

// Altura del relieve de la letra (positivo = relieve hacia arriba, negativo = relieve hacia abajo)
altura_letra = 1; // [-12:0.1:5]

// ¿Incluir eslabón en el primer elemento?
eslabon_primer_elemento = true; // [true:Sí, false:No]

// Color de la base
color_base = "Verde"; // [Amarillo, Azul, Azul Claro, Azul Oscuro, Beige, Blanco, Gris, Marrón, Morado, Naranja, Negro, Rosa, Rojo, Turquesa, Verde, Verde Claro, Verde Oscuro]

// Color de las letras
color_letras = "Beige"; // [Amarillo, Azul, Azul Claro, Azul Oscuro, Beige, Blanco, Gris, Marrón, Morado, Naranja, Negro, Rosa, Rojo, Turquesa, Verde, Verde Claro, Verde Oscuro]

/* [Ajustes de la Base] */
alto = 6;    // [6:0.5:12] Alto del rectángulo principal
ancho = 12;  // Ancho del rectángulo principal
largo = 15;  // Largo del rectángulo principal

// Modo de exportación: "todo" (completo), "base" (solo la base), "texto" (solo las letras)
modo_exportacion = "todo"; // [todo, base, texto]

/* [Hidden] */
diametro_agujero = 10;
profundidad_agujero = 5.5;
diametro = 2;
espacio_entre_modelos = 1;
diametro_externo_cilindro = 6;
diametro_interno_cilindro = 3;
altura_cilindro = 4;
separacion_cilindro = 2;
alto_soporte = 1;
largo_soporte = 2;
tamano_chaflan = 1; // Tamaño del chaflán

// Función para calcular el largo de un elemento individual
function calcular_largo_elemento(es_primero) = 
    (es_primero && !eslabon_primer_elemento) ? (largo - 2) : largo;

// Función para calcular el largo total del modelo
function calcular_largo_total() =
    calcular_largo_elemento(true) + // Primer elemento
    (len(texto) - 1) * (largo + espacio_entre_modelos); // Resto de elementos

// Módulo para crear el modelo individual
module modelo_individual(letra, es_ultimo = false, es_primero = false) {
    // Determinar el largo del modelo
    largo_actual = (es_primero && !eslabon_primer_elemento) ? largo - 2 : largo;
    
    // Calcular la posición del texto
    texto_x = es_primero && !eslabon_primer_elemento ? 
        largo_actual/2 + 0.6 : // Para el primer elemento sin eslabón
        largo/2 + 2;     // Para todos los demás elementos
    
    // Generar la base si el modo es "todo" o "base"
    if (modo_exportacion == "todo" || modo_exportacion == "base") {
        difference() {
            // Rectángulo base con el color base
            color(traducir_color(color_base)) {
                difference() {
                    // Rectángulo base
                    cube([largo_actual, ancho, alto]);
                    
                    // Chaflán esquina inferior izquierda
                    translate([-1, 0, 0])
                        rotate([0, 45, 0])
                            cube([tamano_chaflan * sqrt(2), ancho, tamano_chaflan * sqrt(2)]);
                    
                    // Chaflán esquina superior izquierda
                    translate([0, 0, alto+1])
                        rotate([0, 135, 0])
                            cube([tamano_chaflan * sqrt(2), ancho, tamano_chaflan * sqrt(2)]);
                    
                    // Agujero cilíndrico (solo si no es el primer elemento o si se quiere eslabón)
                    if (!es_primero || eslabon_primer_elemento) {
                        translate([0, ancho/2, alto/2])
                            rotate([90, 0, 0])
                                translate([0, 0, -profundidad_agujero/2])
                                    cylinder(h=profundidad_agujero, d=diametro_agujero, $fn=50);
                    }
                }

                // Cilindro superior (solo si no es el primer elemento o si se quiere eslabón)
                if (!es_primero || eslabon_primer_elemento) {
                    translate([diametro/2, 0, alto/2])
                        rotate([-90, 0, 0])
                            cylinder(h=ancho, d=diametro, $fn=50);
                }

                // Solo agregar cilindro hueco y soportes si no es el último modelo
                if (!es_ultimo) {
                    // Cilindro hueco en el lateral derecho (rotado 90 grados)
                    translate([largo_actual + separacion_cilindro, ancho/2 + altura_cilindro/2, alto/2]) {
                        rotate([90, 0, 0])
                            difference() {
                                cylinder(h=altura_cilindro, d=diametro_externo_cilindro, $fn=50);
                                translate([0, 0, -0.1])
                                    cylinder(h=altura_cilindro + 0.2, d=diametro_interno_cilindro, $fn=50);
                            }
                    }

                    // Soportes rectangulares orientados hacia el centro
                    translate([largo_actual, ancho/2 - altura_cilindro/2, alto/2 + diametro_externo_cilindro/2 - alto_soporte])
                        cube([largo_soporte, altura_cilindro, alto_soporte]);

                    translate([largo_actual, ancho/2 - altura_cilindro/2, alto/2 - diametro_externo_cilindro/2])
                        cube([largo_soporte, altura_cilindro, alto_soporte]);
                }
            }
            
            // Si la altura es negativa, restamos el texto con el color de las letras
            if (altura_letra < 0) {
                color(traducir_color(color_letras))
                    translate([texto_x, ancho/2, alto + altura_letra])
                        linear_extrude(height = abs(altura_letra) + 0.01)
                            text(letra, 
                                 size = tamano_letra,
                                 valign = "center",
                                 halign = "center",
                                 font = fuente_seleccionada);
            }
        }
    }
    
    // Generar las letras si el modo es "todo" o "texto"
    if (modo_exportacion == "todo" || modo_exportacion == "texto") {
        if (altura_letra > 0) {
            color(traducir_color(color_letras))
                translate([texto_x, ancho/2, alto])
                    linear_extrude(height = altura_letra)
                        text(letra, 
                             size = tamano_letra,
                             valign = "center",
                             halign = "center",
                             font = fuente_seleccionada);
        } else if (altura_letra < 0 && modo_exportacion == "texto") {
            // Relleno de letras grabadas para impresión multicolor
            color(traducir_color(color_letras))
                translate([texto_x, ancho/2, alto + altura_letra])
                    linear_extrude(height = abs(altura_letra))
                        text(letra, 
                             size = tamano_letra,
                             valign = "center",
                             halign = "center",
                             font = fuente_seleccionada);
        }
    }
}

// Función para traducir los nombres de los colores
function traducir_color(color_en_espanol) =
    color_en_espanol == "Amarillo" ? "Yellow" :
    color_en_espanol == "Azul" ? "Blue" :
    color_en_espanol == "Azul Claro" ? "LightBlue" :
    color_en_espanol == "Azul Oscuro" ? "DarkBlue" :
    color_en_espanol == "Beige" ? "Beige" :
    color_en_espanol == "Blanco" ? "White" :
    color_en_espanol == "Gris" ? "Gray" :
    color_en_espanol == "Marrón" ? "Brown" :
    color_en_espanol == "Morado" ? "Purple" :
    color_en_espanol == "Naranja" ? "Orange" :
    color_en_espanol == "Negro" ? "Black" :
    color_en_espanol == "Rosa" ? "Pink" :
    color_en_espanol == "Rojo" ? "Red" :
    color_en_espanol == "Turquesa" ? "Turquoise" :
    color_en_espanol == "Verde" ? "Green" :
    color_en_espanol == "Verde Claro" ? "LightGreen" :
    color_en_espanol == "Verde Oscuro" ? "DarkGreen" :
    "Green"; // Color por defecto

// Calcular posiciones teniendo en cuenta el largo variable del primer elemento
function calcular_posicion(i) = 
    i == 0 ? 0 :
    ((!eslabon_primer_elemento ? (largo - 2) : largo) + // Largo del primer elemento
    (i - 1) * (largo + espacio_entre_modelos) + // Elementos intermedios
    espacio_entre_modelos); // Espacio después del primer elemento

// Calcular el desplazamiento necesario para centrar
desplazamiento_x = -calcular_largo_total() / 2;

// Generar todos los modelos con el desplazamiento para centrar
translate([desplazamiento_x, -ancho/2, 0]) // Centrar en X e Y
    for (i = [0:len(texto) - 1]) {
        translate([calcular_posicion(i), 0, 0])
            modelo_individual(str(texto[i]), 
                            i == len(texto) - 1,  // es_ultimo
                            i == 0);              // es_primero
    }