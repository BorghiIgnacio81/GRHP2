// Robust exportarPDF: tries existing page exporter, then loads jsPDF from CDN if needed
function _loadScript(src){
    return new Promise(function(resolve, reject){
        var s = document.createElement('script');
        s.src = src;
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
    });
}

function _ensureJsPDF(){
    if((typeof window.jspdf !== 'undefined' && (window.jspdf.jsPDF || window.jspdf)) || typeof window.jsPDF !== 'undefined'){
        return Promise.resolve();
    }
    // CDN fallback
    var cdn = 'https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js';
    return _loadScript(cdn);
}

function exportarPDF(selector, nombreArchivo = 'documento.pdf') {
    // If page provides a legacy exporter, use it
    if(typeof window.exportarPDF === 'function' && window.exportarPDF !== exportarPDF){
        try{ window.exportarPDF(selector, nombreArchivo); return; }catch(e){ console.warn('legacy exportarPDF failed', e); }
    }

    var elemento = document.querySelector(selector);
    if(!elemento){
        alert('No se encontró el contenido a exportar.');
        return;
    }

    _ensureJsPDF().then(function(){
        var jsPDFConstructor = null;
        if(window.jspdf && window.jspdf.jsPDF) jsPDFConstructor = window.jspdf.jsPDF;
        else if(window.jspdf) jsPDFConstructor = window.jspdf;
        else if(window.jsPDF) jsPDFConstructor = window.jsPDF;
        if(!jsPDFConstructor){
            alert('No se pudo cargar jsPDF para generar el PDF.');
            return;
        }

        const doc = new jsPDFConstructor({ orientation: 'portrait', unit: 'pt', format: 'a4' });

        if(typeof doc.html === 'function'){
            doc.html(elemento, { callback: function(d){ d.save(nombreArchivo); }, x:32, y:32, width:530, windowWidth:800 });
            return;
        }

        if(typeof html2canvas !== 'undefined'){
            html2canvas(elemento, {scale: 2}).then(function(canvas){
                const imgData = canvas.toDataURL('image/png');
                const pageWidth = doc.internal.pageSize.getWidth();
                const imgWidth = pageWidth;
                const imgHeight = (canvas.height * pageWidth) / canvas.width;
                let position = 0;
                doc.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
                while(imgHeight - position > doc.internal.pageSize.getHeight()){
                    position -= doc.internal.pageSize.getHeight();
                    doc.addPage();
                    doc.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
                }
                doc.save(nombreArchivo);
            }).catch(function(e){ alert('Error al renderizar el contenido para PDF.'); console.error('exportarPDF html2canvas error', e); });
            return;
        }

        alert('No es posible generar PDF (falta doc.html o html2canvas/jsPDF).');
    }).catch(function(err){
        console.error('No se pudo cargar jsPDF desde CDN', err);
        alert('No se pudo cargar la librería jsPDF necesaria para generar el PDF.');
    });
}
function exportarPDF(selector, nombreArchivo = 'documento.pdf') {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({
        orientation: 'portrait',
        unit: 'pt',
        format: 'a4'
    });

    const elemento = document.querySelector(selector);
    if (!elemento) {
        alert('No se encontró el contenido a exportar.');
        return;
    }

    // Usa doc.html para capturar el contenido visual
    doc.html(elemento, {
        callback: function (doc) {
            doc.save(nombreArchivo);
        },
        x: 32,
        y: 32,
        width: 530, // más grande y centrado en A4
        windowWidth: 800 // ayuda a renderizar bien el contenido
    });
}