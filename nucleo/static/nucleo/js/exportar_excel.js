function exportarTablaAExcel(selectorTabla, nombreArchivo = 'tabla.csv', excluirUltimaColumna = false) {
    const tabla = document.querySelector(selectorTabla);
    if (!tabla) {
        alert('No se encontró la tabla a exportar.');
        return;
    }
    let csv = [];
    for (let row of tabla.rows) {
        let cols = Array.from(row.cells);
        if (excluirUltimaColumna) {
            cols = cols.slice(0, -1);
        }
        // Usar punto y coma como separador para compatibilidad con Excel en español
        let fila = cols.map(cell => {
            let text = cell.innerText.replace(/"/g, '""');
            return `"${text}"`;
        }).join(';');
        csv.push(fila);
    }
    let csvContent = csv.join('\r\n');
    let blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    let link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = nombreArchivo;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}