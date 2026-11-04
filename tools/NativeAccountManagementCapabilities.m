// Inspect the official Music UI on a disposable runner without signing in.
#import <AppKit/AppKit.h>
#import <ApplicationServices/ApplicationServices.h>
#import <Foundation/Foundation.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static NSString *AXStatus(AXError error) {
    switch (error) {
        case kAXErrorSuccess: return @"success";
        case kAXErrorAPIDisabled: return @"accessibility_disabled";
        case kAXErrorCannotComplete: return @"cannot_complete";
        case kAXErrorAttributeUnsupported: return @"attribute_unsupported";
        case kAXErrorNoValue: return @"no_value";
        default: return @"other";
    }
}

static void ReadMenus(AXUIElementRef element, NSUInteger depth,
                      NSUInteger *budget, NSMutableDictionary *report) {
    if (!element || depth > 4 || !*budget) return;
    --*budget;
    CFTypeRef raw = NULL;
    if (AXUIElementCopyAttributeValue(element, kAXTitleAttribute, &raw) == kAXErrorSuccess && raw) {
        if (CFGetTypeID(raw) == CFStringGetTypeID()) {
            NSString *title = (__bridge NSString *)raw;
            NSDictionary *labels = @{
                @"Account": @"account_menu_seen",
                @"Account Settings…": @"account_settings_item_seen",
                @"Account Settings...": @"account_settings_item_seen",
                @"View My Account…": @"account_settings_item_seen",
                @"View My Account...": @"account_settings_item_seen",
                @"Sign In…": @"sign_in_item_seen",
                @"Sign In...": @"sign_in_item_seen",
                @"Authorizations": @"authorizations_menu_seen",
                @"Authorize This Computer…": @"authorize_item_seen",
                @"Authorize This Computer...": @"authorize_item_seen",
                @"Deauthorize This Computer…": @"deauthorize_item_seen",
                @"Deauthorize This Computer...": @"deauthorize_item_seen",
            };
            NSString *key = labels[title];
            if (key) report[key] = @YES;
        }
        CFRelease(raw);
    }
    raw = NULL;
    if (AXUIElementCopyAttributeValue(element, kAXChildrenAttribute, &raw) == kAXErrorSuccess && raw) {
        if (CFGetTypeID(raw) == CFArrayGetTypeID()) {
            CFArrayRef children = (CFArrayRef)raw;
            CFIndex n = MIN(CFArrayGetCount(children), 64);
            for (CFIndex i = 0; i < n && *budget; ++i) {
                CFTypeRef child = CFArrayGetValueAtIndex(children, i);
                if (child && CFGetTypeID(child) == AXUIElementGetTypeID())
                    ReadMenus((AXUIElementRef)child, depth + 1, budget, report);
            }
        }
        CFRelease(raw);
    }
}

int main(void) { @autoreleasepool {
    const char *ci = getenv("GITHUB_ACTIONS");
    if (!ci || strcmp(ci, "true") || getenv("APPLE_ID") || getenv("APPLE_PASSWORD")) return 2;
    alarm(40);
    NSMutableDictionary *report = [@{
        @"schema": @"ipa-lab-account-management-capabilities-v1",
        @"credentials_used": @NO, @"account_login_attempted": @NO,
        @"authorization_request_attempted": @NO, @"deauthorization_attempted": @NO,
        @"authorization_count_retrieved": @NO, @"permission_prompt_requested": @NO,
        @"ui_action_performed": @NO, @"account_management_working": @NO,
        @"account_menu_seen": @NO, @"account_settings_item_seen": @NO,
        @"sign_in_item_seen": @NO, @"authorizations_menu_seen": @NO,
        @"authorize_item_seen": @NO, @"deauthorize_item_seen": @NO,
        @"music_launch_succeeded": @NO, @"menu_read_status": @"not_attempted"
    } mutableCopy];
    CFDictionaryRef session = CGSessionCopyCurrentDictionary();
    report[@"console_session_available"] = @(session != NULL);
    report[@"on_console"] = @NO;
    if (session) {
        id value = ((__bridge NSDictionary *)session)[(__bridge NSString *)kCGSessionOnConsoleKey];
        if ([value isKindOfClass:NSNumber.class]) report[@"on_console"] = @([value boolValue]);
        CFRelease(session);
    }
    NSWorkspace *workspace = NSWorkspace.sharedWorkspace;
    for (NSString *scheme in @[@"itms", @"itmss", @"macappstores"]) {
        NSURL *url = [NSURL URLWithString:[scheme stringByAppendingString:@"://?action=modifyAccount"]];
        NSURL *handler = [workspace URLForApplicationToOpenURL:url];
        NSString *bundle = handler ? [NSBundle bundleWithURL:handler].bundleIdentifier : nil;
        NSArray *allowed = @[@"com.apple.Music", @"com.apple.TV", @"com.apple.AppStore"];
        report[[scheme stringByAppendingString:@"_handler"]] =
            [allowed containsObject:bundle ?: @""] ? bundle : (handler ? @"other" : @"absent");
    }
    NSURL *music = [workspace URLForApplicationWithBundleIdentifier:@"com.apple.Music"];
    report[@"music_installed"] = @(music != nil);
    report[@"accessibility_trusted"] = @(AXIsProcessTrusted());
    if (music) {
        BOOL alreadyRunning = [NSRunningApplication runningApplicationsWithBundleIdentifier:@"com.apple.Music"].count > 0;
        __block BOOL completed = NO;
        __block NSRunningApplication *application = nil;
        NSWorkspaceOpenConfiguration *configuration = NSWorkspaceOpenConfiguration.configuration;
        configuration.activates = NO;
        configuration.addsToRecentItems = NO;
        configuration.promptsUserIfNeeded = NO;
        [workspace openApplicationAtURL:music configuration:configuration
                     completionHandler:^(NSRunningApplication *app, NSError *error) {
            dispatch_async(dispatch_get_main_queue(), ^{
                application = error ? nil : app;
                completed = YES;
            });
        }];
        NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:15];
        while (!completed && deadline.timeIntervalSinceNow > 0)
            [NSRunLoop.currentRunLoop runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.1]];
        report[@"music_launch_succeeded"] = @(completed && application != nil);
        report[@"music_launch_timed_out"] = @(!completed);
        if (application && [report[@"accessibility_trusted"] boolValue]) {
            AXUIElementRef target = AXUIElementCreateApplication(application.processIdentifier);
            NSDate *menuDeadline = [NSDate dateWithTimeIntervalSinceNow:4];
            do {
                CFTypeRef menu = NULL;
                AXError result = AXUIElementCopyAttributeValue(target, kAXMenuBarAttribute, &menu);
                report[@"menu_read_status"] = AXStatus(result);
                if (result == kAXErrorSuccess && menu && CFGetTypeID(menu) == AXUIElementGetTypeID()) {
                    NSUInteger budget = 256;
                    ReadMenus((AXUIElementRef)menu, 0, &budget, report);
                }
                if (menu) CFRelease(menu);
                if ([report[@"account_menu_seen"] boolValue]) break;
                [NSRunLoop.currentRunLoop runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.2]];
            } while (menuDeadline.timeIntervalSinceNow > 0);
            CFRelease(target);
        }
        if (application && !alreadyRunning) [application terminate];
    }
    NSData *data = [NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingSortedKeys error:nil];
    if (!data) return 3;
    [NSFileHandle.fileHandleWithStandardOutput writeData:data];
    [NSFileHandle.fileHandleWithStandardOutput writeData:[@"\n" dataUsingEncoding:NSUTF8StringEncoding]];
    return 0;
}}
