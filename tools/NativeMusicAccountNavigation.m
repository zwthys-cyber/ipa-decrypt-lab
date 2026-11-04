// Bounded navigation to the official sign-in UI. No credentials or account mutation.
#import <AppKit/AppKit.h>
#import <ApplicationServices/ApplicationServices.h>
#import <Foundation/Foundation.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <math.h>

static id ReadAttribute(AXUIElementRef element, CFStringRef attribute) {
    CFTypeRef value = NULL;
    if (!element || AXUIElementCopyAttributeValue(element, attribute, &value) != kAXErrorSuccess) {
        if (value) CFRelease(value);
        return nil;
    }
    return CFBridgingRelease(value);
}
static NSString *Text(id value) { return [value isKindOfClass:NSString.class] ? value : @""; }
static NSString *Label(id raw) {
    NSString *s = Text(raw);
    if (s.length > 1024) return @"unknown";
    s = [[s stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet] lowercaseString];
    while ([s hasSuffix:@"…"] || [s hasSuffix:@"."] || [s hasSuffix:@":"])
        s = [s substringToIndex:s.length-1];
    NSDictionary *labels = @{
        @"sign out":@"sign_out", @"computer authorizations":@"computer_authorizations", @"authorized devices":@"authorized_devices",
        @"your apple account or password was incorrect":@"credentials_rejected", @"your apple id or password was incorrect":@"credentials_rejected",
        @"account":@"account", @"account settings":@"account_settings", @"view my account":@"account_settings",
        @"sign in":@"sign_in", @"sign in to the itunes store":@"sign_in_heading",
        @"sign in to music":@"sign_in_heading", @"sign in to your apple account":@"sign_in_heading",
        @"sign in with your apple account":@"sign_in_heading", @"sign in with your apple id":@"sign_in_heading",
        @"apple account":@"apple_account", @"apple id":@"apple_account",
        @"email or phone number":@"apple_account", @"email address":@"apple_account",
        @"password":@"password", @"cancel":@"cancel", @"continue":@"continue",
        @"welcome to music":@"welcome", @"welcome to apple music":@"welcome", @"start listening":@"welcome_start",
        @"music and privacy":@"privacy", @"apple music and privacy":@"privacy",
        @"upgrade account security":@"security_upgrade", @"don't upgrade":@"decline_upgrade",
        @"not now":@"not_now", @"verification code":@"verification",
        @"enter verification code":@"verification", @"two-factor authentication":@"verification",
        @"terms and conditions":@"terms", @"agree":@"agree",
        @"subscribe":@"subscribe", @"try it free":@"subscribe",
        @"authorizations":@"authorizations", @"authorize this computer":@"authorize",
        @"deauthorize this computer":@"deauthorize", @"deauthorize all":@"deauthorize_all"
    };
    if(labels[s])return labels[s];
    if([s containsString:@"verification code"])return @"verification";
    if([s containsString:@"account"] && ([s containsString:@"is locked"] || [s containsString:@"has been locked"]))return @"account_locked";
    if([s containsString:@"account"] && ([s containsString:@"is disabled"] || [s containsString:@"has been disabled"]))return @"account_disabled";
    if([s containsString:@"incorrect"] && [s containsString:@"password"])return @"credentials_rejected";
    if([s containsString:@"has not yet been used"] || [s containsString:@"review your account"])return @"store_account_review";
    if([s containsString:@"error connecting"] || [s containsString:@"could not connect"] || [s containsString:@"cannot connect"])return @"connection_error";
    if([s containsString:@"could not sign in"] || [s containsString:@"couldn't sign in"] ||
       [s containsString:@"unable to sign in"] || [s containsString:@"error signing in"])return @"signin_error";
    if([s containsString:@"unknown error"])return @"unknown_error";
    if([s containsString:@"try again later"])return @"try_later";
    if([s containsString:@"upgrade"] && [s containsString:@"account"] && [s containsString:@"security"])return @"security_upgrade";
    if([s containsString:@"two-factor authentication"])return @"two_factor_mention";
    return @"unknown";
}
static NSString *Role(id raw) {
    NSString *role = Text(raw);
    NSArray *known = @[@"AXApplication",@"AXWindow",@"AXSheet",@"AXDialog",@"AXGroup",@"AXButton",
        @"AXTextField",@"AXStaticText",@"AXMenuBar",@"AXMenuBarItem",@"AXMenu",@"AXMenuItem",
        @"AXCheckBox",@"AXRadioButton",@"AXProgressIndicator",@"AXWebArea",@"AXScrollArea",@"AXLink",@"AXImage"];
    return [known containsObject:role] ? role : @"other";
}
static NSString *ErrorCategory(AXError error) {
    switch (error) {
        case kAXErrorSuccess:return @"success";
        case kAXErrorAPIDisabled:return @"accessibility_disabled";
        case kAXErrorCannotComplete:return @"cannot_complete";
        case kAXErrorActionUnsupported:return @"action_unsupported";
        default:return @"other";
    }
}
static BOOL CanPress(NSString *action, NSString *role, NSString *label, BOOL enabled) {
    if (!enabled) return NO;
    if ([action isEqual:@"open_account_menu"])
        return [role isEqual:@"AXMenuBarItem"] && [label isEqual:@"account"];
    if ([action isEqual:@"open_account_settings"])
        return [role isEqual:@"AXMenuItem"] && [label isEqual:@"account_settings"];
    if ([action isEqual:@"dismiss_welcome"])
        return [role isEqual:@"AXButton"] && [label isEqual:@"welcome_start"];
    if ([action isEqual:@"open_signin_dialog"])
        return [role isEqual:@"AXMenuItem"] && [label isEqual:@"sign_in"];
    return NO;
}
static BOOL Pressable(AXUIElementRef element) {
    CFArrayRef names=NULL;
    AXError error=AXUIElementCopyActionNames(element,&names);
    BOOL result=error==kAXErrorSuccess && names && [(__bridge NSArray *)names containsObject:(__bridge NSString *)kAXPressAction];
    if (names) CFRelease(names);
    return result;
}
static BOOL HasLabel(NSDictionary *node,NSString *label) {
    for (NSString *key in @[@"title",@"description",@"text",@"placeholder"])
        if ([node[key] isEqual:label]) return YES;
    return NO;
}
static void Collect(AXUIElementRef element, NSUInteger depth, NSMutableArray *nodes) {
    if (!element || depth > 12 || nodes.count >= 320) return;
    NSString *role = Role(ReadAttribute(element,kAXRoleAttribute));
    NSString *subrole = Text(ReadAttribute(element,kAXSubroleAttribute));
    NSString *title = Label(ReadAttribute(element,kAXTitleAttribute));
    NSString *description = Label(ReadAttribute(element,kAXDescriptionAttribute));
    NSString *value = [role isEqual:@"AXStaticText"] ? Label(ReadAttribute(element,kAXValueAttribute)) : @"not_read";
    id enabled = ReadAttribute(element,kAXEnabledAttribute);
    Boolean settable = false;
    AXUIElementIsAttributeSettable(element,kAXValueAttribute,&settable);
    [nodes addObject:@{
        @"element":(__bridge id)element, @"role":role, @"title":title, @"description":description,
        @"text":value, @"placeholder":Label(ReadAttribute(element,CFSTR("AXPlaceholderValue"))),
        @"pressable":Pressable(element)?@YES:@NO, @"depth":@(depth), @"enabled":@([enabled isKindOfClass:NSNumber.class] && [enabled boolValue]),
        @"secure":[subrole isEqual:@"AXSecureTextField"] ? @YES : @NO,
        @"value_settable":settable ? @YES : @NO
    }];
    id children = ReadAttribute(element,kAXChildrenAttribute);
    if (![children isKindOfClass:NSArray.class]) return;
    NSUInteger count = 0;
    for (id child in children) {
        if (++count > 80 || nodes.count >= 320) break;
        if (CFGetTypeID((__bridge CFTypeRef)child) == AXUIElementGetTypeID())
            Collect((__bridge AXUIElementRef)child,depth+1,nodes);
    }
}
static NSArray *Nodes(AXUIElementRef root) {
    NSMutableArray *nodes = [NSMutableArray array];
    Collect(root,0,nodes);
    return nodes;
}
static NSDictionary *PublicSnapshot(NSArray *nodes) {
    NSMutableDictionary *roles = [NSMutableDictionary dictionary], *labels = [NSMutableDictionary dictionary];
    NSMutableArray *controls = [NSMutableArray array], *recognized = [NSMutableArray array];
    for (NSDictionary *node in nodes) {
        NSString *role = node[@"role"];
        roles[role] = @([roles[role] unsignedIntegerValue] + 1);
        for (NSString *key in @[@"title",@"description",@"text",@"placeholder"]) {
            NSString *label = node[key];
            if (label && ![label isEqual:@"unknown"] && ![label isEqual:@"not_read"]) {
                labels[label] = @([labels[label] unsignedIntegerValue]+1);
                if (recognized.count<48) [recognized addObject:@{
                    @"role":role,@"label":label,@"depth":node[@"depth"],
                    @"enabled":node[@"enabled"],@"pressable":node[@"pressable"]?:@NO
                }];
            }
        }
        if (([role isEqual:@"AXTextField"] || [role isEqual:@"AXButton"] ||
             [role isEqual:@"AXSheet"] || [role isEqual:@"AXDialog"]) && controls.count < 48) {
            NSMutableDictionary *summary = [node mutableCopy];
            [summary removeObjectForKey:@"element"];
            [controls addObject:summary];
        }
    }
    return @{@"node_count":@(nodes.count), @"traversal_cap_reached":nodes.count>=320 ? @YES:@NO,
             @"roles":roles,@"labels":labels,@"controls":controls,@"recognized":recognized};
}
static NSDictionary *WindowSnapshot(AXUIElementRef app) {
    id windows = ReadAttribute(app,kAXWindowsAttribute);
    NSMutableArray *all = [NSMutableArray array];
    if ([windows isKindOfClass:NSArray.class]) {
        NSUInteger count = 0;
        for (id window in windows) {
            if (++count > 8 || all.count >= 320) break;
            if (CFGetTypeID((__bridge CFTypeRef)window) == AXUIElementGetTypeID())
                Collect((__bridge AXUIElementRef)window,0,all);
        }
    }
    return PublicSnapshot(all);
}
static BOOL Press(NSArray *nodes, NSString *action, NSMutableDictionary *report) {
    NSMutableArray *matches = [NSMutableArray array];
    for (NSDictionary *node in nodes)
        if (CanPress(action,node[@"role"],node[@"title"],[node[@"enabled"] boolValue])) [matches addObject:node];
    if (matches.count != 1) { report[action] = @"not_uniquely_available"; return NO; }
    AXError result = AXUIElementPerformAction((__bridge AXUIElementRef)matches[0][@"element"],kAXPressAction);
    report[action] = ErrorCategory(result);
    return result == kAXErrorSuccess;
}
static void Pump(NSTimeInterval seconds) {
    NSDate *end = [NSDate dateWithTimeIntervalSinceNow:seconds];
    while (end.timeIntervalSinceNow>0)
        [NSRunLoop.currentRunLoop runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.1]];
}
static BOOL WelcomeContext(NSDictionary *snapshot) {
    NSDictionary *labels=snapshot[@"labels"], *roles=snapshot[@"roles"];
    if ([labels[@"welcome"] unsignedIntegerValue]!=1 || [roles[@"AXTextField"] unsignedIntegerValue]) return NO;
    for (NSString *label in @[@"security_upgrade",@"verification",@"terms",@"agree",@"subscribe",@"password",
                             @"apple_account",@"sign_in",@"sign_in_heading"])
        if ([labels[label] unsignedIntegerValue]) return NO;
    return YES;
}
static BOOL DismissWelcome(AXUIElementRef app, NSMutableDictionary *report) {
    id windows=ReadAttribute(app,kAXWindowsAttribute);
    if (![windows isKindOfClass:NSArray.class]) return NO;
    for (id window in windows) {
        if (CFGetTypeID((__bridge CFTypeRef)window)!=AXUIElementGetTypeID()) continue;
        for (NSDictionary *node in Nodes((__bridge AXUIElementRef)window)) {
            if (![node[@"role"] isEqual:@"AXSheet"]) continue;
            NSArray *sheet=Nodes((__bridge AXUIElementRef)node[@"element"]);
            if (!WelcomeContext(PublicSnapshot(sheet))) continue;
            return Press(sheet,@"dismiss_welcome",report);
        }
    }
    report[@"dismiss_welcome"]=@"no_recognized_welcome_sheet";
    return NO;
}
static BOOL ClickNotNowText(AXUIElementRef element,NSMutableDictionary *report) {
    if (![Role(ReadAttribute(element,kAXRoleAttribute)) isEqual:@"AXStaticText"] ||
        ![Label(ReadAttribute(element,kAXValueAttribute)) isEqual:@"not_now"]) return NO;
    BOOL allowed=CGPreflightPostEventAccess();
    report[@"post_event_access"]=allowed?@YES:@NO;
    if (!allowed) return NO;
    id position=ReadAttribute(element,kAXPositionAttribute), size=ReadAttribute(element,kAXSizeAttribute);
    if (!position || !size || CFGetTypeID((__bridge CFTypeRef)position)!=AXValueGetTypeID() ||
        CFGetTypeID((__bridge CFTypeRef)size)!=AXValueGetTypeID()) return NO;
    CGPoint origin={0}; CGSize extent={0};
    if (!AXValueGetValue((__bridge AXValueRef)position,kAXValueCGPointType,&origin) ||
        !AXValueGetValue((__bridge AXValueRef)size,kAXValueCGSizeType,&extent) ||
        !isfinite(origin.x) || !isfinite(origin.y) || !isfinite(extent.width) || !isfinite(extent.height) ||
        extent.width<=0 || extent.width>500 || extent.height<=0 || extent.height>100) return NO;
    CGPoint point=CGPointMake(origin.x+extent.width/2,origin.y+extent.height/2);
    if (!CGRectContainsPoint(CGDisplayBounds(CGMainDisplayID()),point)) return NO;
    AXUIElementRef system=AXUIElementCreateSystemWide(), hit=NULL;
    AXError error=AXUIElementCopyElementAtPosition(system,point.x,point.y,&hit);
    CFRelease(system);
    pid_t originalPid=0, hitPid=0;
    BOOL same=error==kAXErrorSuccess && hit &&
        AXUIElementGetPid(element,&originalPid)==kAXErrorSuccess &&
        AXUIElementGetPid(hit,&hitPid)==kAXErrorSuccess && originalPid==hitPid &&
        [Role(ReadAttribute(hit,kAXRoleAttribute)) isEqual:@"AXStaticText"] &&
        [Label(ReadAttribute(hit,kAXValueAttribute)) isEqual:@"not_now"];
    if (hit) CFRelease(hit);
    report[@"not_now_hit_test_verified"]=same?@YES:@NO;
    if (!same) return NO;
    CGEventRef down=CGEventCreateMouseEvent(NULL,kCGEventLeftMouseDown,point,kCGMouseButtonLeft);
    CGEventRef up=CGEventCreateMouseEvent(NULL,kCGEventLeftMouseUp,point,kCGMouseButtonLeft);
    if (!down || !up) {if(down)CFRelease(down);if(up)CFRelease(up);return NO;}
    CGEventPost(kCGHIDEventTap,down); CGEventPost(kCGHIDEventTap,up);
    CFRelease(down); CFRelease(up);
    report[@"not_now_coordinate_click_posted"]=@YES;
    report[@"decline_optional_sheet"]=@"click_posted";
    return YES;
}
static BOOL DeclineOptionalSheet(AXUIElementRef app,NSMutableDictionary *report) {
    id windows=ReadAttribute(app,kAXWindowsAttribute);
    if (![windows isKindOfClass:NSArray.class]) return NO;
    for (id window in windows) {
        if (CFGetTypeID((__bridge CFTypeRef)window)!=AXUIElementGetTypeID()) continue;
        for (NSDictionary *node in Nodes((__bridge AXUIElementRef)window)) {
            if (![node[@"role"] isEqual:@"AXSheet"]) continue;
            NSArray *sheet=Nodes((__bridge AXUIElementRef)node[@"element"]);
            NSDictionary *summary=PublicSnapshot(sheet);
            if (![summary[@"labels"][@"not_now"] unsignedIntegerValue] ||
                [summary[@"roles"][@"AXTextField"] unsignedIntegerValue]) continue;
            NSMutableArray *targets=[NSMutableArray array];
            for (NSDictionary *candidate in sheet) if (HasLabel(candidate,@"not_now")) [targets addObject:candidate];
            if (targets.count!=1) {report[@"decline_optional_sheet"]=@"ambiguous";return NO;}
            id element=targets[0][@"element"];
            for (NSUInteger level=0;level<3 && element;level++) {
                AXUIElementRef target=(__bridge AXUIElementRef)element;
                NSDictionary *scope=PublicSnapshot(Nodes(target));
                if (![scope[@"labels"][@"not_now"] unsignedIntegerValue] ||
                    [scope[@"labels"][@"continue"] unsignedIntegerValue] ||
                    [scope[@"labels"][@"subscribe"] unsignedIntegerValue] ||
                    [scope[@"roles"][@"AXTextField"] unsignedIntegerValue]) break;
                if (Pressable(target)) {
                    AXError result=AXUIElementPerformAction(target,kAXPressAction);
                    report[@"decline_optional_sheet"]=ErrorCategory(result);
                    return result==kAXErrorSuccess;
                }
                element=ReadAttribute(target,kAXParentAttribute);
                if (element && CFGetTypeID((__bridge CFTypeRef)element)!=AXUIElementGetTypeID()) break;
            }
            if (ClickNotNowText((__bridge AXUIElementRef)targets[0][@"element"],report)) return YES;
            report[@"decline_optional_sheet"]=@"no_bounded_pressable_target";
            return NO;
        }
    }
    report[@"decline_optional_sheet"]=@"no_recognized_optional_sheet";
    return NO;
}
static BOOL Contract(void) {
    if (!WelcomeContext(@{@"labels":@{@"welcome":@1},@"roles":@{}}) ||
        WelcomeContext(@{@"labels":@{@"welcome":@1,@"security_upgrade":@1},@"roles":@{}}) ||
        WelcomeContext(@{@"labels":@{@"welcome":@1},@"roles":@{@"AXTextField":@1}}) ||
        WelcomeContext(@{@"labels":@{},@"roles":@{}})) return NO;
    if (!CanPress(@"open_account_menu",@"AXMenuBarItem",Label(@"Account"),YES) ||
        !CanPress(@"open_signin_dialog",@"AXMenuItem",Label(@"Sign In…"),YES)) return NO;
    for (NSString *forbidden in @[@"Deauthorize All",@"Deauthorize This Computer…",@"Authorize This Computer…",
                                  @"Upgrade Account Security",@"Agree",@"Continue",@"Subscribe",@"Sign In and Pay"])
        if (CanPress(@"open_signin_dialog",@"AXMenuItem",Label(forbidden),YES)) return NO;
    if (CanPress(@"open_signin_dialog",@"AXButton",@"sign_in",YES) ||
        CanPress(@"open_signin_dialog",@"AXMenuItem",@"sign_in",NO) ||
        CanPress(@"unknown",@"AXMenuItem",@"sign_in",YES)) return NO;
    if (![Label(@"private-account-value@example.invalid") isEqual:@"unknown"]) return NO;
    NSDictionary *fixture = @{@"element":@"PRIVATE-SENTINEL", @"role":@"AXTextField",
        @"title":@"unknown",@"description":@"unknown",@"text":@"not_read",@"depth":@1,
        @"enabled":@YES,@"secure":@YES,@"value_settable":@YES};
    NSData *data = [NSJSONSerialization dataWithJSONObject:PublicSnapshot(@[fixture]) options:0 error:nil];
    return data && [[[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding] rangeOfString:@"PRIVATE-SENTINEL"].location == NSNotFound;
}
static NSRunningApplication *NavigateToSignIn(NSMutableDictionary *report) {
    NSURL *url = [NSWorkspace.sharedWorkspace URLForApplicationWithBundleIdentifier:@"com.apple.Music"];
    if (url && [report[@"accessibility_trusted"] boolValue]) {
        __block BOOL done=NO;
        __block NSRunningApplication *app=nil;
        NSWorkspaceOpenConfiguration *configuration=NSWorkspaceOpenConfiguration.configuration;
        configuration.activates=YES; configuration.addsToRecentItems=NO; configuration.promptsUserIfNeeded=NO;
        [NSWorkspace.sharedWorkspace openApplicationAtURL:url configuration:configuration
            completionHandler:^(NSRunningApplication *result,NSError *error) {
                dispatch_async(dispatch_get_main_queue(), ^{app=error?nil:result;done=YES;});
            }];
        NSDate *deadline=[NSDate dateWithTimeIntervalSinceNow:12];
        while (!done && deadline.timeIntervalSinceNow>0) Pump(0.1);
        if (app) {
            report[@"music_launch_succeeded"]=@YES;
            AXUIElementRef target=AXUIElementCreateApplication(app.processIdentifier);
            AXUIElementSetMessagingTimeout(target,1.0);
            NSDate *startupDeadline=[NSDate dateWithTimeIntervalSinceNow:8];
            do {
                report[@"before_navigation"]=WindowSnapshot(target);
                if ([report[@"before_navigation"][@"labels"][@"welcome"] unsignedIntegerValue]) break;
                Pump(0.5);
            } while (startupDeadline.timeIntervalSinceNow>0);
            if (DismissWelcome(target,report)) {
                NSDate *optionalDeadline=[NSDate dateWithTimeIntervalSinceNow:10];
                do {
                    report[@"after_welcome"]=WindowSnapshot(target);
                    if([report[@"after_welcome"][@"labels"][@"not_now"] unsignedIntegerValue])break;
                    Pump(0.3);
                }while(optionalDeadline.timeIntervalSinceNow>0);
            }
            report[@"after_welcome"]=WindowSnapshot(target);
            if (DeclineOptionalSheet(target,report)) {
                NSDate *dismissDeadline=[NSDate dateWithTimeIntervalSinceNow:6];
                do {
                    Pump(0.3);
                    report[@"after_optional_sheet"]=WindowSnapshot(target);
                    if(![report[@"after_optional_sheet"][@"labels"][@"not_now"] unsignedIntegerValue])break;
                }while(dismissDeadline.timeIntervalSinceNow>0);
            }
            report[@"after_optional_sheet"]=WindowSnapshot(target);
            id menu=ReadAttribute(target,kAXMenuBarAttribute);
            if (menu && CFGetTypeID((__bridge CFTypeRef)menu)==AXUIElementGetTypeID()) {
                NSArray *nodes=Nodes((__bridge AXUIElementRef)menu);
                report[@"menus_before"]=PublicSnapshot(nodes);
                if (Press(nodes,@"open_account_menu",report)) {
                    Pump(0.3);
                    NSDate *signinDeadline=[NSDate dateWithTimeIntervalSinceNow:8];
                    do {
                        nodes=Nodes((__bridge AXUIElementRef)menu);
                        BOOL ready=NO;
                        for(NSDictionary *node in nodes)
                            if(CanPress(@"open_signin_dialog",node[@"role"],node[@"title"],[node[@"enabled"] boolValue]))ready=YES;
                        if(ready)break;
                        Pump(0.3);
                    }while(signinDeadline.timeIntervalSinceNow>0);
                    report[@"menus_open"]=PublicSnapshot(nodes);
                    if (Press(nodes,@"open_signin_dialog",report)) {
                        report[@"status"]=@"signin_menu_invoked";
                        Pump(5);
                    } else report[@"status"]=@"signin_menu_unavailable";
                } else report[@"status"]=@"account_menu_unavailable";
            }
            report[@"after_navigation"]=WindowSnapshot(target);
            CFRelease(target);
            return app;
        }
    }
    return nil;
}
#ifndef LAB_MUSIC_UI_LIBRARY
int main(int argc, const char **argv) { @autoreleasepool {
    const char *ci = getenv("GITHUB_ACTIONS");
    if (!ci || strcmp(ci,"true") || getenv("APPLE_ID") || getenv("APPLE_PASSWORD")) return 2;
    if (argc==2 && !strcmp(argv[1],"--contract")) {
        if (!Contract()) return 3;
        puts("Official account navigation contract passed.");
        return 0;
    }
    if (argc != 1) return 2;
    alarm(55);
    NSMutableDictionary *report = [@{
        @"schema":@"ipa-lab-music-account-navigation-v1",
        @"credentials_used":@NO,@"credential_submit_attempted":@NO,
        @"authorization_request_attempted":@NO,@"deauthorization_attempted":@NO,
        @"security_upgrade_accepted":@NO,@"authorization_count_retrieved":@NO,
        @"account_management_working":@NO,@"permission_prompt_requested":@NO,
        @"music_launch_succeeded":@NO,@"accessibility_trusted":AXIsProcessTrusted()?@YES:@NO,
        @"status":@"unavailable"
    } mutableCopy];
    NSRunningApplication *app=NavigateToSignIn(report);
    if(app)[app terminate];
    NSData *data=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingSortedKeys error:nil];
    if(!data)return 3;
    [NSFileHandle.fileHandleWithStandardOutput writeData:data];
    [NSFileHandle.fileHandleWithStandardOutput writeData:[@"\n" dataUsingEncoding:NSUTF8StringEncoding]];
    return 0;
}}

#endif
