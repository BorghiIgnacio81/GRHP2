/* Reusable export utilities for tables and DOM elements
   Provides: exportTableToCSV, exportElementToPDF, bindExportButtons
   Buttons can use data attributes:
     data-export-target (selector for table or element)
     data-export-filename (filename to download)
     data-export-format (csv|excel|pdf)
     data-export-server-url (optional) - if present and format=excel will navigate to server URL
*/
(function(window){
  'use strict';
  
  console.log('🚀 export-utils.js loading...');

  function downloadBlob(blob, filename){
    const link = document.createElement('a');
    link.href = window.URL.createObjectURL(blob);
    link.download = filename || 'download';
    document.body.appendChild(link);
    link.click();
    setTimeout(()=>{
      window.URL.revokeObjectURL(link.href);
      document.body.removeChild(link);
    }, 100);
  }

  // Improved CSV export function with better column detection
  function tableToCSVImproved(table){
    console.log('🔄 Using improved CSV export...');
    const rows = Array.from(table.querySelectorAll('tr'));
    if(rows.length === 0) return '';

    // Use the same column selection logic as PDF export
    const headerRow = table.querySelector('thead tr') || table.querySelector('tr');
    const headerCells = headerRow ? Array.from(headerRow.querySelectorAll('th, td')) : [];
    const colCount = headerCells.length;
    
    // Define which columns we want to keep (same as PDF)
  const wantedHeaders = ['id', 'empleado', 'nombre', 'apellido', 'tipo', 'desde', 'hasta', 'días', 'dias', 'estado', 'dni', 'fecha', 'feriado', 'descripcion', 'descripción', 'tabla', 'idregistro', 'cambio', 'usuario', 'email', 'nacionalidad', 'civil', 'sexo', 'localidad', 'direccion', 'fecha_nac', 'nacimiento'];
    const keep = new Array(colCount).fill(false);
    
    // Mark columns to keep based on header content
    for(let c=0; c<colCount; c++){
      const h = headerCells[c];
      const txt = h ? (h.innerText||'').toLowerCase().trim() : '';
      
      // Keep columns that match our wanted headers
      const isWanted = wantedHeaders.some(wanted => txt.includes(wanted));
      if(isWanted) {
        keep[c] = true;
      }
      console.log(`CSV Column ${c}: "${txt}" -> ${isWanted ? 'KEEP' : 'SKIP'}`);
    }
    
    // Build CSV with only kept columns
    const lines = [];
    rows.forEach((row, rIdx) => {
      const cols = Array.from(row.querySelectorAll('th, td'));
      const values = [];
      
      for(let c=0; c<colCount; c++){
        if(!keep[c]) continue;
        
        const cell = cols[c];
        let text = cell ? (cell.innerText || cell.textContent || '').trim() : '';
        
        // Clean up text
        text = text.replace(/\n/g, ' ').replace(/\r/g, ' ').replace(/\t/g, ' ');
        // Escape quotes for CSV
        text = text.replace(/"/g, '""');
        
        values.push('"' + text + '"');
      }
      
      if(values.length > 0) {
        // Use comma for standard CSV compatibility
        lines.push(values.join(','));
      }
    });
    
    console.log('📊 CSV generated with', lines.length, 'rows and', keep.filter(k => k).length, 'columns');
    return lines.join('\r\n');
  }

  function exportTableToCSV(target, filename){
    let tableEl = typeof target === 'string' ? document.querySelector(target) : target;
    if(!tableEl){
      console.warn('export-utils: table not found', target);
      return;
    }
    
    // Use improved CSV export for better column detection
    const csv = tableToCSVImproved(tableEl);
    
    // Prefix UTF-8 BOM so Excel recognizes UTF-8 and separators reliably
    const BOM = '\uFEFF';
    const outName = filename || 'export.csv';
    const blob = new Blob([BOM + csv], {type: 'text/csv;charset=utf-8;'});
    downloadBlob(blob, outName);
  }

  // Basic excel export: same as CSV but with .xls extension (Excel will open it)
  function exportTableToExcel(target, filename){
    // For compatibility and correctness we export CSV with BOM and .csv extension
    const name = filename || 'export.csv';
    // ensure .csv extension
    const finalName = name.toLowerCase().endsWith('.csv') ? name : name.replace(/\.(xls|xlsx)$/i, '') + '.csv';
    exportTableToCSV(target, finalName);
  }

  // Export an arbitrary element to PDF using html2canvas + jsPDF if available
  async function exportElementToPDF(target, filename, opts){
    console.log('📄 exportElementToPDF called:', { target, filename });
    let el = typeof target === 'string' ? document.querySelector(target) : target;
    console.log('🎯 Element found:', el);
    if(!el){
      console.warn('export-utils: element not found', target);
      return;
    }
    // If a legacy exporter exists on the page, prefer it (keeps backwards compatibility)
    console.log('🔍 Checking for legacy exportarPDF:', typeof window.exportarPDF);
    
    // TEMPORARILY DISABLED - legacy function produces blank PDFs
    // We want to use our new column-selection logic instead
    if(false && typeof window.exportarPDF === 'function'){
      console.log('⚠️ Using legacy exportarPDF function');
      try{
        // exportarPDF expects a selector and filename in this project
        window.exportarPDF(target, filename || 'export.pdf');
        console.log('✅ Legacy exportarPDF completed successfully');
        return;
      }catch(e){
        console.warn('export-utils: exportarPDF failed, falling back to html2canvas/jsPDF', e);
      }
    }
    console.log('🆕 Using new column-selection PDF export');

    // Prefer generating a tabular PDF for table targets using jsPDF + autotable
    async function ensureScript(url){
      return new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = url;
        s.async = true;
        s.onload = () => resolve();
        s.onerror = () => reject(new Error('Failed to load ' + url));
        document.head.appendChild(s);
      });
    }

    // If element is a table, build a data array and use AutoTable for reliable text PDF
    console.log('🔍 Checking if element is table:', { tagName: el.tagName, isTable: el.tagName === 'TABLE' });
    const tableEl = (el.tagName === 'TABLE') ? el : (el.querySelector ? el.querySelector('table') : null);
    console.log('📊 Table element:', tableEl);
    if(tableEl){
      // gather headers and rows - use positive selection instead of negative filtering
      const headerRow = tableEl.querySelector('thead tr') || tableEl.querySelector('tr');
      const headerCells = headerRow ? Array.from(headerRow.querySelectorAll('th, td')) : [];
      const colCount = headerCells.length;
      
      // Define which columns we want to keep based on header text
  const wantedHeaders = ['id', 'empleado', 'nombre', 'apellido', 'tipo', 'desde', 'hasta', 'días', 'dias', 'estado', 'dni', 'fecha', 'feriado', 'descripcion', 'descripción', 'tabla', 'idregistro', 'cambio', 'usuario', 'email', 'nacionalidad', 'civil', 'sexo', 'localidad', 'direccion', 'fecha_nac', 'nacimiento'];
      const keep = new Array(colCount).fill(false);
      
      // Mark columns to keep based on header content
      for(let c=0; c<colCount; c++){
        const h = headerCells[c];
        const txt = h ? (h.innerText||'').toLowerCase().trim() : '';
        
        // Keep columns that match our wanted headers
        const isWanted = wantedHeaders.some(wanted => txt.includes(wanted));
        if(isWanted) {
          keep[c] = true;
        }
        console.log(`Column ${c}: "${txt}" -> ${isWanted ? 'KEEP' : 'SKIP'}`);
      }
      
      // Build headers and body arrays only with kept columns
      const headers = [];
      const keepIndices = [];
      for(let c=0; c<colCount; c++) {
        if(keep[c]) {
          headers.push(headerCells[c] ? headerCells[c].innerText.trim() : ('Col '+(c+1)));
          keepIndices.push(c);
        }
      }
      
      const rows = Array.from(tableEl.querySelectorAll('tbody tr')).length ? Array.from(tableEl.querySelectorAll('tbody tr')) : Array.from(tableEl.querySelectorAll('tr'));
      const body = rows.map(r => {
        const cells = Array.from(r.querySelectorAll('th, td'));
        const out = [];
        keepIndices.forEach(c => {
          const cell = cells[c];
          out.push(cell ? (cell.innerText || '').trim() : '');
        });
        return out;
      }).filter(r=> r.some(c=> c !== ''));

      // If after filtering we have no table data, don't attempt AutoTable (can produce blank PDFs).
      const hasTableData = headers.length > 0 && body.length > 0;
      
      console.log('export-utils PDF Debug:', {
        tableId: tableEl.id || 'no-id',
        headers: headers,
        bodyRows: body.length,
        selectedColumns: keepIndices,
        keptColumnHeaders: headers,
        hasTableData: hasTableData,
        firstBodyRow: body[0] || 'no data'
      });

      // Ensure jsPDF and autotable are present (load from CDN if needed)
      console.log('📚 Checking jsPDF and AutoTable availability...');
      const jsPDFReady = (typeof window.jspdf !== 'undefined' && (window.jspdf.jsPDF || window.jspdf)) || (typeof window.jsPDF !== 'undefined');
      const autoReady = (typeof window.jspdf !== 'undefined' && window.jspdf.autoTable) || (typeof window.jsPDF !== 'undefined' && window.jsPDF.autoTable) || (typeof window.jspdfAutoTable !== 'undefined');
      console.log('📊 Library status:', { jsPDFReady, autoReady });
      
      const loaders = [];
      if(!jsPDFReady) {
        console.log('⬇️ Loading jsPDF...');
        loaders.push(ensureScript('https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js'));
      }
      if(!autoReady) {
        console.log('⬇️ Loading AutoTable...');
        loaders.push(ensureScript('https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.5.28/jspdf.plugin.autotable.min.js'));
      }
      
      try{
        await Promise.all(loaders);
        console.log('✅ Libraries loaded successfully');
      }catch(err){
        console.warn('export-utils: failed to load jsPDF/AutoTable; falling back to image-based PDF', err);
        // fallback to original image-based method
      }

      // resolve jsPDF constructor
      console.log('🔧 Resolving jsPDF constructor...');
      let jsPDFConstructor = null;
      if(window.jspdf && window.jspdf.jsPDF) {
        jsPDFConstructor = window.jspdf.jsPDF;
        console.log('✅ Found window.jspdf.jsPDF');
      } else if(window.jsPDF) {
        jsPDFConstructor = window.jsPDF;
        console.log('✅ Found window.jsPDF');
      } else if(window.jspdf) {
        jsPDFConstructor = window.jspdf;
        console.log('✅ Found window.jspdf');
      }
      
      console.log('🔍 jsPDF Constructor found:', !!jsPDFConstructor);
      console.log('🔍 AutoTable availability check...');
      
      // Try to create a test jsPDF instance and check for autoTable
      let autoTableAvailable = false;
      if(jsPDFConstructor) {
        try {
          const testDoc = new jsPDFConstructor('l','pt','a4'); // landscape for testing
          autoTableAvailable = typeof testDoc.autoTable === 'function';
          console.log('📊 AutoTable test result:', autoTableAvailable);
        } catch(e) {
          console.warn('Could not test AutoTable:', e);
        }
      }
      
      console.log('📊 Final AutoTable available:', autoTableAvailable);
      
      if(jsPDFConstructor && autoTableAvailable){
        if(hasTableData){
          const doc = new jsPDFConstructor('l','pt','a4'); // landscape for AutoTable
          // Build autotable columns
          const cols = headers.map(h => ({header: h, dataKey: h}));
          // convert body array to objects keyed by header
          const dataObjects = body.map(rowArr => {
            const obj = {};
            headers.forEach((h, idx) => obj[h] = rowArr[idx] || '');
            return obj;
          });
          // call autotable but guard with try/catch; if it fails, fallback to image rendering
          console.log('🎯 Attempting AutoTable PDF generation...');
          try{
            if(typeof doc.autoTable === 'function'){
              console.log('✅ Using doc.autoTable');
              doc.autoTable({head:[headers], body: body, startY: 20});
            } else if(typeof window.jspdfAutoTable !== 'undefined' && typeof jsPDFConstructor.autoTable === 'function'){
              console.log('✅ Using jsPDFConstructor.autoTable');
              doc.autoTable({head:[headers], body: body, startY: 20});
            } else if(doc && doc.autoTable){
              console.log('✅ Using doc.autoTable (fallback)');
              doc.autoTable({head:[headers], body: body, startY: 20});
            } else {
              throw new Error('AutoTable not available on jsPDF instance');
            }
            console.log('🎉 AutoTable completed successfully, saving PDF...');
            doc.save(filename || 'export.pdf');
            return;
          }catch(autoErr){
            console.warn('export-utils: AutoTable generation failed, falling back to image-based PDF', autoErr);
            // fall through to image fallback below
          }
        } else {
          // no tabular data to render via AutoTable — skip to image fallback
        }
      } else if(jsPDFConstructor && hasTableData) {
        // FALLBACK: Simple text-based PDF without AutoTable
        console.log('🆘 AutoTable not available, using simple text PDF...');
        try {
          const doc = new jsPDFConstructor('l','pt','a4'); // 'l' = landscape (apaisado)
          const pageWidth = doc.internal.pageSize.getWidth();
          const pageHeight = doc.internal.pageSize.getHeight();
          const margin = 40;
          let y = 60;
          
          // Title
          doc.setFontSize(16);
          doc.text('Reporte de Empleados', margin, y);
          y += 30;
          
          // Adjust column widths - optimize for better text fitting
          const totalWidth = pageWidth - 2 * margin;
          const columnWidths = {
            'ID': totalWidth * 0.03,           // 3% - reducido más (solo necesita 2 dígitos)
            'Nombre': totalWidth * 0.08,       // 8% - mantener
            'Apellido': totalWidth * 0.08,     // 8% - mantener
            'DNI': totalWidth * 0.07,          // 7% - mantener
            'Fec_Nac': totalWidth * 0.09,      // 9% - aumentado para fechas completas
            'Email': totalWidth * 0.18,        // 18% - aumentado para emails completos
            'Sexo': totalWidth * 0.06,         // 6% - mantener
            'Localidad': totalWidth * 0.11,    // 11% - aumentado para nombres de ciudades
            'Estado': totalWidth * 0.06,       // 6% - reducido (Activo/Inactivo)
            'default': totalWidth * 0.08       // 8% - otros campos
          };
          
          // Rename headers for better fit
          const adjustedHeaders = headers.map(h => {
            const lower = h.toLowerCase();
            if (lower.includes('fecha') && lower.includes('nac')) return 'Fec_Nac';
            return h;
          });
          
          // Calculate column positions and widths
          const colPositions = [];
          const colWidths = [];
          let currentX = margin;
          
          adjustedHeaders.forEach((header, i) => {
            colPositions.push(currentX);
            const headerLower = header.toLowerCase();
            let width;
            
            if (headerLower === 'id') width = columnWidths['ID'];
            else if (headerLower === 'nombre') width = columnWidths['Nombre'];
            else if (headerLower === 'apellido') width = columnWidths['Apellido'];
            else if (headerLower === 'dni') width = columnWidths['DNI'];
            else if (headerLower === 'fec_nac') width = columnWidths['Fec_Nac'];
            else if (headerLower === 'email') width = columnWidths['Email'];
            else if (headerLower === 'sexo') width = columnWidths['Sexo'];
            else if (headerLower === 'localidad') width = columnWidths['Localidad'];
            else if (headerLower === 'estado') width = columnWidths['Estado'];
            else width = columnWidths['default'];
            
            colWidths.push(width);
            currentX += width;
          });
          
          // Draw table borders
          doc.setDrawColor(0, 0, 0);
          doc.setLineWidth(0.5);
          
          // Headers with proper borders
          doc.setFontSize(8);  // Reducido de 9 a 8
          const headerY = y;
          const headerHeight = 15;
          
          // Draw header background rectangle
          doc.setFillColor(240, 240, 240);
          doc.rect(margin, headerY - headerHeight, currentX - margin, headerHeight, 'F');
          
          // Draw header text and borders
          adjustedHeaders.forEach((header, i) => {
            // Center text in cell
            const textX = colPositions[i] + colWidths[i] / 2;
            doc.text(header, textX, headerY - 5, { align: 'center' });
            
            // Vertical line at start of column
            doc.line(colPositions[i], headerY - headerHeight, colPositions[i], headerY);
          });
          
          // Last vertical line and top/bottom borders
          doc.line(currentX, headerY - headerHeight, currentX, headerY);
          doc.line(margin, headerY - headerHeight, currentX, headerY - headerHeight); // Top
          doc.line(margin, headerY, currentX, headerY); // Bottom
          
          y += 5;
          
          // Data rows with proper borders
          doc.setFontSize(7);  // Reducido de 8 a 7 para que quepa más texto
          body.forEach((row, rowIndex) => {
            if(y > 520) { // Adjusted for landscape
              doc.addPage();
              y = 60;
              // Repeat headers with proper formatting
              doc.setFontSize(8);  // Consistente con headers
              const headerY = y;
              const headerHeight = 15;
              
              doc.setFillColor(240, 240, 240);
              doc.rect(margin, headerY - headerHeight, currentX - margin, headerHeight, 'F');
              
              adjustedHeaders.forEach((header, i) => {
                const textX = colPositions[i] + colWidths[i] / 2;
                doc.text(header, textX, headerY - 5, { align: 'center' });
                doc.line(colPositions[i], headerY - headerHeight, colPositions[i], headerY);
              });
              
              doc.line(currentX, headerY - headerHeight, currentX, headerY);
              doc.line(margin, headerY - headerHeight, currentX, headerY - headerHeight);
              doc.line(margin, headerY, currentX, headerY);
              
              y += 5;
              doc.setFontSize(7);  // Consistente con data rows
            }
            
            const rowHeight = 12;
            const rowY = y;
            
            // Alternate row background
            if (rowIndex % 2 === 1) {
              doc.setFillColor(248, 248, 248);
              doc.rect(margin, rowY, currentX - margin, rowHeight, 'F');
            }
            
            row.forEach((cell, i) => {
              const text = String(cell || '');
              const headerLower = adjustedHeaders[i] ? adjustedHeaders[i].toLowerCase() : '';
              
              // Adjust text length based on column width - más generoso
              let maxLength;
              if (headerLower === 'id') maxLength = 3;
              else if (headerLower === 'nombre') maxLength = 12;
              else if (headerLower === 'apellido') maxLength = 12;
              else if (headerLower === 'dni') maxLength = 9;
              else if (headerLower === 'fec_nac') maxLength = 10; // Para fechas completas YYYY-MM-DD
              else if (headerLower === 'email') maxLength = 25;   // Para emails completos
              else if (headerLower === 'sexo') maxLength = 7;
              else if (headerLower === 'localidad') maxLength = 15; // Para nombres de ciudades
              else if (headerLower === 'estado') maxLength = 7;   // Activo/Inactivo
              else maxLength = 12;
              
              const truncatedText = text.substring(0, maxLength);
              
              // Center text in cell
              const textX = colPositions[i] + colWidths[i] / 2;
              doc.text(truncatedText, textX, rowY + 8, { align: 'center' });
              
              // Vertical line at start of column
              doc.line(colPositions[i], rowY, colPositions[i], rowY + rowHeight);
            });
            
            // Last vertical line and bottom border
            doc.line(currentX, rowY, currentX, rowY + rowHeight);
            doc.line(margin, rowY + rowHeight, currentX, rowY + rowHeight);
            
            y += rowHeight;
          });
          
          console.log('✅ Simple text PDF generated successfully');
          doc.save(filename || 'export.pdf');
          return;
        } catch(simpleErr) {
          console.warn('export-utils: Simple PDF generation failed:', simpleErr);
          // Continue to image fallback
        }
      }
      // if we couldn't create a tabular PDF, fall back to image render below
    }

    // Fallback: original image-based method using html2canvas + jsPDF
    var hasHtml2Canvas = (typeof html2canvas !== 'undefined');
    var hasJsPDF = (typeof window.jspdf !== 'undefined' && (window.jspdf.jsPDF || window.jspdf)) || (typeof window.jsPDF !== 'undefined');
    if(!hasHtml2Canvas || !hasJsPDF){
      console.warn('export-utils: html2canvas or jsPDF not available for PDF export', {hasHtml2Canvas, hasJsPDF});
      return;
    }
    try{
      const canvas = await html2canvas(el, {scale: opts && opts.scale || 2, useCORS: true, backgroundColor: '#ffffff'});
      const imgData = canvas.toDataURL('image/png');
      var jsPDFConstructor = null;
      if(window.jspdf && window.jspdf.jsPDF) jsPDFConstructor = window.jspdf.jsPDF;
      else if(window.jspdf) jsPDFConstructor = window.jspdf;
      else if(window.jsPDF) jsPDFConstructor = window.jsPDF;
      else {
        console.error('export-utils: jsPDF constructor not found after detection');
        return;
      }
      const pdf = new jsPDFConstructor('l', 'pt', 'a4'); // landscape for fallback
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const imgWidth = pageWidth;
      const imgHeight = (canvas.height * pageWidth) / canvas.width;
      let position = 0;
      pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
      // if content longer than one page, add pages
      let remaining = imgHeight - pageHeight;
      let page = 1;
      while(remaining > 0){
        const y = -page * pageHeight;
        pdf.addPage();
        pdf.addImage(imgData, 'PNG', 0, y, imgWidth, imgHeight);
        page++;
        remaining -= pageHeight;
      }
      pdf.save(filename || 'export.pdf');
    }catch(e){
      console.error('export-utils: PDF export failed', e);
    }
  }

  function handleClick(e){
    console.log('🔥 Export button clicked!');
    const btn = e.currentTarget;
    const target = btn.getAttribute('data-export-target');
    const filename = btn.getAttribute('data-export-filename');
    const format = (btn.getAttribute('data-export-format') || 'excel').toLowerCase();
    const serverUrl = btn.getAttribute('data-export-server-url');
    
    console.log('📊 Export params:', { target, filename, format, serverUrl });

    if(format === 'excel' && serverUrl){
      // prefer server-side export if provided
      window.location.href = serverUrl;
      return;
    }

    if(format === 'csv' || format === 'excel'){
      exportTableToExcel(target, filename || (format === 'csv' ? 'export.csv' : 'export.xls'));
      return;
    }
    if(format === 'pdf'){
      exportElementToPDF(target, filename || 'export.pdf');
      return;
    }
  }

  function bindExportButtons(context){
    const root = context || document;
    const buttons = root.querySelectorAll('[data-export-target]');
    buttons.forEach(btn => {
      // avoid duplicate binds
      if(btn.__exportBound) return;
      btn.addEventListener('click', handleClick);
      btn.__exportBound = true;
    });
  }

  window.exportUtils = {
    exportTableToCSV,
    exportTableToExcel,
    exportElementToPDF,
    bindExportButtons
  };

  // Auto-bind on DOMContentLoaded
  document.addEventListener('DOMContentLoaded', function(){
    bindExportButtons();
  });

})(window);
