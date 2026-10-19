try {
    $word = New-Object -ComObject Word.Application
    Write-Host "Word COM is available"
    $doc = $word.Documents.Open("C:\Users\Admin\Documents\OpenCode\my school project THE MAIN\docs\Memoire_Fin_Detudes_RESIVO.docx")
    $pdfPath = "C:\Users\Admin\Documents\OpenCode\my school project THE MAIN\docs\Memoire_Fin_Detudes_RESIVO.pdf"
    # 17 represents wdFormatPDF
    $doc.SaveAs([ref]$pdfPath, [ref]17)
    $doc.Close()
    $word.Quit()
    Write-Host "Successfully exported PDF: $pdfPath"
} catch {
    Write-Host "Word conversion not available: $($_.Exception.Message)"
}
