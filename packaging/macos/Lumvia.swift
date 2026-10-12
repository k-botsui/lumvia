import AppKit
import WebKit

final class Lumvia: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var status: NSTextField!
    var process: Process?
    let control = Pipe()
    var origin: URL?
    var readyData = Data()
    var terminating = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        let menu = NSMenu()
        let appItem = NSMenuItem()
        menu.addItem(appItem)
        let appMenu = NSMenu()
        appItem.submenu = appMenu
        appMenu.addItem(withTitle: "Lumviaを終了", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let editItem = NSMenuItem()
        menu.addItem(editItem)
        let edit = NSMenu(title: "編集")
        editItem.submenu = edit
        for (title, action, key) in [("コピー", "copy:", "c"), ("貼り付け", "paste:", "v"), ("切り取り", "cut:", "x"), ("すべて選択", "selectAll:", "a")] {
            edit.addItem(withTitle: title, action: Selector(action), keyEquivalent: key)
        }
        NSApp.mainMenu = menu
        let visible = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1280, height: 900)
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: min(1180, visible.width - 40), height: min(800, visible.height - 60)), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "Lumvia"
        window.minSize = NSSize(width: 760, height: 540)
        window.center()
        let configuration = WKWebViewConfiguration()
        web = WKWebView(frame: window.contentView!.bounds, configuration: configuration)
        web.autoresizingMask = [.width, .height]
        web.navigationDelegate = self
        web.uiDelegate = self
        window.contentView!.addSubview(web)
        status = NSTextField(wrappingLabelWithString: "Lumviaを準備しています。初回は少し時間がかかります。")
        status.frame = NSRect(x: 80, y: 360, width: 980, height: 80)
        status.autoresizingMask = [.width, .minYMargin, .maxYMargin]
        window.contentView!.addSubview(status)
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        guard let resources = Bundle.main.resourceURL else { fail(); return }
        let proc = Process()
        process = proc
        proc.executableURL = resources.appendingPathComponent("runtime/python/bin/python3")
        proc.arguments = [resources.appendingPathComponent("supervisor.py").path]
        proc.environment = ["HOME": NSHomeDirectory(), "PATH": "/usr/bin:/bin", "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "LANG": "en_US.UTF-8"]
        proc.standardInput = control
        let output = Pipe()
        proc.standardOutput = output
        proc.standardError = FileHandle.nullDevice
        output.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let bytes = handle.availableData
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.readyData.append(bytes)
                while let end = self.readyData.firstIndex(of: 10) {
                    let line = self.readyData.prefix(upTo: end)
                    self.readyData.removeSubrange(...end)
                    self.received(Data(line))
                }
            }
        }
        proc.terminationHandler = { [weak self] _ in
            DispatchQueue.main.async {
                guard let self = self else { return }
                if self.terminating { NSApp.reply(toApplicationShouldTerminate: true) } else { self.fail() }
            }
        }
        do { try proc.run() } catch { fail() }
    }

    func received(_ data: Data) {
        guard let message = try? JSONSerialization.jsonObject(with: data) as? [String: String],
              let value = message["url"], let url = URL(string: value), url.host == "127.0.0.1", url.scheme == "http",
              let credentialsPath = message["credentials_path"] else { fail(); return }
        origin = url
        // Authenticate locally without exposing an initial password in the UI or logs.
        guard let credentialsData = FileManager.default.contents(atPath: credentialsPath),
              let credentials = try? JSONSerialization.jsonObject(with: credentialsData) as? [String: String] else { show(); return }
        var request = URLRequest(url: url.appendingPathComponent("api/v1/auth/login"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(value, forHTTPHeaderField: "Origin")
        request.httpBody = try? JSONSerialization.data(withJSONObject: ["email": credentials["admin_email"] ?? "", "password": credentials["admin_password"] ?? ""])
        let session = URLSession(configuration: .ephemeral)
        session.dataTask(with: request) { [weak self] _, response, _ in
            guard let self = self else { return }
            let http = response as? HTTPURLResponse
            var headers: [String: String] = [:]
            http?.allHeaderFields.forEach { key, value in headers[String(describing: key)] = String(describing: value) }
            let cookies = http?.statusCode == 200 ? HTTPCookie.cookies(withResponseHeaderFields: headers, for: url) : []
            DispatchQueue.main.async {
                let group = DispatchGroup()
                for cookie in cookies {
                    group.enter()
                    self.web.configuration.websiteDataStore.httpCookieStore.setCookie(cookie) { group.leave() }
                }
                group.notify(queue: .main) { self.show() }
            }
            session.finishTasksAndInvalidate()
        }.resume()
    }

    func show() {
        status.isHidden = true
        if let url = origin { web.load(URLRequest(url: url)) }
    }
    func fail() {
        status.isHidden = false
        status.stringValue = "Lumviaを起動できませんでした。終了して、もう一度開いてください。データは削除されていません。\n問題が続く場合はお問い合わせください。"
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let proc = process, proc.isRunning else { return .terminateNow }
        terminating = true
        try? control.fileHandleForWriting.write(contentsOf: Data("stop\n".utf8))
        try? control.fileHandleForWriting.close()
        return .terminateLater
    }
    func external(_ url: URL) {
        if ["https", "http", "mailto"].contains(url.scheme ?? "") { NSWorkspace.shared.open(url) }
    }
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if action.shouldPerformDownload { decisionHandler(.download); return }
        guard let url = action.request.url else { decisionHandler(.cancel); return }
        if action.targetFrame?.isMainFrame == true, url.scheme != "blob",
           !(url.host == origin?.host && url.port == origin?.port && url.scheme == origin?.scheme) {
            if action.navigationType == .linkActivated { external(url) }
            decisionHandler(.cancel)
        } else { decisionHandler(.allow) }
    }
    func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        let attachment = (response.response as? HTTPURLResponse)?.value(forHTTPHeaderField: "Content-Disposition")?.lowercased().hasPrefix("attachment") ?? false
        decisionHandler(attachment || !response.canShowMIMEType ? .download : .allow)
    }
    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) { download.delegate = self }
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = (suggestedFilename as NSString).lastPathComponent
        panel.beginSheetModal(for: window) { result in completionHandler(result == .OK ? panel.url : nil) }
    }
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url { external(url) }
        return nil
    }
    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.beginSheetModal(for: window) { result in completionHandler(result == .OK ? panel.urls : nil) }
    }
    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let alert = NSAlert()
        alert.messageText = message
        alert.addButton(withTitle: "OK")
        alert.addButton(withTitle: "キャンセル")
        alert.beginSheetModal(for: window) { completionHandler($0 == .alertFirstButtonReturn) }
    }
}

let application = NSApplication.shared
let delegate = Lumvia()
application.delegate = delegate
application.setActivationPolicy(.regular)
application.run()
