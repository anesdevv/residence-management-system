// Print the text Vision recognizes in each image, one JSON line per image:
// {"path": ..., "lines": [...], "boxes": [{"text", "x", "y", "w", "h"}]}, boxes as fractions of the image (origin top-left).
import Foundation
import Vision
import AppKit

for path in CommandLine.arguments.dropFirst() {
    guard let image = NSImage(contentsOfFile: path),
          let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.minimumTextHeight = 0.006
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([request])
    var lines: [String] = []
    var boxes: [[String: Any]] = []
    for obs in request.results ?? [] {
        guard let top = obs.topCandidates(1).first else { continue }
        let b = obs.boundingBox
        lines.append(top.string)
        boxes.append(["text": top.string, "x": b.minX, "y": 1 - b.maxY, "w": b.width, "h": b.height])
    }
    let data = try! JSONSerialization.data(withJSONObject: ["path": path, "lines": lines, "boxes": boxes])
    print(String(data: data, encoding: .utf8)!)
}
