// One official Music sign-in flow and a read-only account authorization-count query.
#define LAB_MUSIC_UI_LIBRARY
#include "NativeMusicAccountNavigation.m"

static NSDictionary *FindForm(AXUIElementRef app,BOOL passwordStage) {
    id windows=ReadAttribute(app,kAXWindowsAttribute);
    if (![windows isKindOfClass:NSArray.class]) return nil;
    NSMutableArray *forms=[NSMutableArray array];
    for(id window in windows) {
        if(CFGetTypeID((__bridge CFTypeRef)window)!=AXUIElementGetTypeID())continue;
        NSArray *nodes=Nodes((__bridge AXUIElementRef)window);
        NSMutableArray *emails=[NSMutableArray array],*passwords=[NSMutableArray array],*submits=[NSMutableArray array];
        BOOL heading=NO;
        for(NSDictionary *node in nodes) {
            if(HasLabel(node,@"sign_in_heading"))heading=YES;
            if([node[@"role"] isEqual:@"AXTextField"] && [node[@"value_settable"] boolValue]) {
                if([node[@"secure"] boolValue])[passwords addObject:node];
                else if(HasLabel(node,@"apple_account"))[emails addObject:node];
            }
            if([node[@"role"] isEqual:@"AXButton"] && HasLabel(node,@"sign_in") && [node[@"pressable"] boolValue])
                [submits addObject:node];
        }
        if(!heading || submits.count!=1)continue;
        if(passwordStage ? passwords.count!=1 : (emails.count!=1 || passwords.count!=0))continue;
        [forms addObject:@{@"field":(passwordStage?passwords:emails)[0][@"element"],@"submit":submits[0][@"element"]}];
    }
    return forms.count==1?forms[0]:nil;
}
static BOOL Fill(NSDictionary *form,NSString *value) {
    AXUIElementRef field=(__bridge AXUIElementRef)form[@"field"];
    if(!field)return NO;
    if(AXUIElementSetAttributeValue(field,kAXFocusedAttribute,kCFBooleanTrue)!=kAXErrorSuccess)return NO;
    if(AXUIElementSetAttributeValue(field,kAXValueAttribute,(__bridge CFStringRef)value)!=kAXErrorSuccess)return NO;
    Pump(0.5);
    // Never read a password field back.
    return YES;
}
static BOOL Submit(NSDictionary *form) {
    AXUIElementRef button=(__bridge AXUIElementRef)form[@"submit"];
    id enabled=ReadAttribute(button,kAXEnabledAttribute);
    if(![enabled isKindOfClass:NSNumber.class] || ![enabled boolValue] ||
       ![Label(ReadAttribute(button,kAXTitleAttribute)) isEqual:@"sign_in"])return NO;
    return AXUIElementPerformAction(button,kAXPressAction)==kAXErrorSuccess;
}
static BOOL SignedIn(AXUIElementRef app) {
    id menu=ReadAttribute(app,kAXMenuBarAttribute);
    if(!menu || CFGetTypeID((__bridge CFTypeRef)menu)!=AXUIElementGetTypeID())return NO;
    NSArray *nodes=Nodes((__bridge AXUIElementRef)menu);
    for(NSDictionary *node in nodes)
        if([node[@"role"] isEqual:@"AXMenuItem"] && HasLabel(node,@"sign_out") && [node[@"enabled"] boolValue])return YES;
    return NO;
}
static NSNumber *ExplicitComputerCount(NSString *text) {
    if(![text isKindOfClass:NSString.class] || text.length>1024)return nil;
    // Current usage statements only: never parse a policy saying "up to five".
    NSArray *patterns=@[
        @"^\\s*([0-5]) computers? (?:is|are) authorized to (?:play|use|access)\\b",
        @"^\\s*You have authorized ([0-5]) computers?\\b"
    ];
    for(NSString *pattern in patterns) {
        NSRegularExpression *regex=[NSRegularExpression regularExpressionWithPattern:pattern options:NSRegularExpressionCaseInsensitive error:nil];
        NSTextCheckingResult *match=[regex firstMatchInString:text options:0 range:NSMakeRange(0,text.length)];
        if(match)return @([[text substringWithRange:[match rangeAtIndex:1]] integerValue]);
    }
    return nil;
}
static NSNumber *ReadComputerCount(AXUIElementRef app,NSMutableDictionary *report) {
    id windows=ReadAttribute(app,kAXWindowsAttribute);
    if(![windows isKindOfClass:NSArray.class])return nil;
    NSMutableSet *counts=[NSMutableSet set];
    for(id window in windows) {
        if(CFGetTypeID((__bridge CFTypeRef)window)!=AXUIElementGetTypeID())continue;
        NSArray *nodes=Nodes((__bridge AXUIElementRef)window);
        NSDictionary *labels=PublicSnapshot(nodes)[@"labels"];
        if(![labels[@"computer_authorizations"] unsignedIntegerValue] &&
           ![labels[@"authorized_devices"] unsignedIntegerValue])continue;
        report[@"authorization_section_observed"]=@YES;
        for(NSDictionary *node in nodes) {
            if(![node[@"role"] isEqual:@"AXStaticText"])continue;
            AXUIElementRef element=(__bridge AXUIElementRef)node[@"element"];
            NSNumber *count=ExplicitComputerCount(Text(ReadAttribute(element,kAXValueAttribute)));
            if(!count)count=ExplicitComputerCount(Text(ReadAttribute(element,kAXTitleAttribute)));
            if(count)[counts addObject:count];
        }
    }
    if(counts.count==1){report[@"explicit_current_count_observed"]=@YES;return counts.anyObject;}
    return nil;
}
static void Screen(AXUIElementRef app,NSMutableDictionary *report,NSString *stage) {
    NSDictionary *snapshot=WindowSnapshot(app);
    NSMutableDictionary *screens=report[@"screens"];
    if(!screens){screens=[NSMutableDictionary dictionary];report[@"screens"]=screens;}
    screens[stage]=@{@"roles":snapshot[@"roles"],@"labels":snapshot[@"labels"]};
}
static BOOL QueryContract(void) {
    return Contract() && [ExplicitComputerCount(@"5 computers are authorized to play content purchased with this Apple Account.") isEqual:@5] &&
        [ExplicitComputerCount(@"1 computer is authorized to play your purchases.") isEqual:@1] &&
        !ExplicitComputerCount(@"You can authorize up to 5 computers.") &&
        !ExplicitComputerCount(@"10 devices are associated with your Apple Account.") &&
        !ExplicitComputerCount(@"Private value 5 computers") &&
        !CanPress(@"open_account_settings",@"AXMenuItem",@"deauthorize_all",YES);
}
static void Query(AXUIElementRef app,NSDictionary *private,NSMutableDictionary *report) {
    NSDictionary *form=FindForm(app,NO);
    if(!form){report[@"status"]=@"email_form_unavailable";return;}
    report[@"email_form_ready"]=@YES;
    if(!Fill(form,private[@"apple_id"])){report[@"status"]=@"email_fill_failed";return;}
    report[@"credentials_used"]=@YES;
    if(!Submit(form)){report[@"status"]=@"email_submit_failed";return;}
    report[@"email_submit_attempted"]=@YES;
    NSDate *deadline=[NSDate dateWithTimeIntervalSinceNow:20];
    NSDictionary *passwordForm=nil;
    do {Pump(0.5);passwordForm=FindForm(app,YES);if(passwordForm)break;} while(deadline.timeIntervalSinceNow>0);
    Screen(app,report,@"after_email");
    if(!passwordForm){report[@"status"]=@"password_form_unavailable";return;}
    report[@"password_form_ready"]=@YES;
    if(!Fill(passwordForm,private[@"password"])){report[@"status"]=@"password_fill_failed";return;}
    if(!Submit(passwordForm)){report[@"status"]=@"password_submit_failed";return;}
    report[@"password_submit_attempted"]=@YES;
    deadline=[NSDate dateWithTimeIntervalSinceNow:25];
    BOOL signedIn=NO;
    do {Pump(0.5);signedIn=SignedIn(app);if(signedIn)break;} while(deadline.timeIntervalSinceNow>0);
    Screen(app,report,@"after_password");
    if(!signedIn){report[@"status"]=@"signin_unconfirmed";return;}
    report[@"signed_in_menu_observed"]=@YES;
    id menu=ReadAttribute(app,kAXMenuBarAttribute);
    if(!menu || CFGetTypeID((__bridge CFTypeRef)menu)!=AXUIElementGetTypeID()) {report[@"status"]=@"account_menu_unavailable";return;}
    if(!Press(Nodes((__bridge AXUIElementRef)menu),@"open_account_menu",report)) {report[@"status"]=@"account_menu_unavailable";return;}
    Pump(0.3);
    if(!Press(Nodes((__bridge AXUIElementRef)menu),@"open_account_settings",report)) {report[@"status"]=@"account_settings_unavailable";return;}
    report[@"account_settings_invoked"]=@YES;
    deadline=[NSDate dateWithTimeIntervalSinceNow:15];
    NSNumber *count=nil;
    do {Pump(0.5);count=ReadComputerCount(app,report);if(count)break;} while(deadline.timeIntervalSinceNow>0);
    Screen(app,report,@"account_settings");
    if(!count){report[@"status"]=@"count_not_observed";return;}
    report[@"authorized_computer_count"]=count;
    report[@"authorization_count_retrieved"]=@YES;
    report[@"status"]=@"count_retrieved";
}
int main(int argc,const char **argv){@autoreleasepool{
    const char *ci=getenv("GITHUB_ACTIONS");
    if(!ci || strcmp(ci,"true") || getenv("APPLE_ID") || getenv("APPLE_PASSWORD"))return 2;
    if(argc==2 && !strcmp(argv[1],"--contract")){
        if(!QueryContract())return 3;
        puts("Official Music private-query and count-parser contracts passed.");return 0;
    }
    BOOL preflight=argc==2 && !strcmp(argv[1],"--preflight");
    if(argc!=1 && !preflight)return 2;
    alarm(115);
    NSDictionary *private=nil;
    if(!preflight){
        NSData *data=[NSFileHandle.fileHandleWithStandardInput readDataOfLength:8193];
        if(data.length==0 || data.length>8192)return 2;
        id object=[NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
        if(![object isKindOfClass:NSDictionary.class])return 2;
        private=object;
        for(NSString *key in @[@"apple_id",@"password"]){
            id value=private[key];
            if(![value isKindOfClass:NSString.class] || [value length]==0 || [value length]>1024 ||
               [value rangeOfCharacterFromSet:NSCharacterSet.controlCharacterSet].location!=NSNotFound)return 2;
        }
    }
    NSMutableDictionary *report=[@{
        @"schema":@"ipa-lab-music-account-query-v1",@"status":@"navigation_failed",
        @"credentials_used":@NO,@"email_submit_attempted":@NO,@"password_submit_attempted":@NO,
        @"signed_in_menu_observed":@NO,@"account_settings_invoked":@NO,
        @"authorization_section_observed":@NO,@"explicit_current_count_observed":@NO,
        @"authorization_count_retrieved":@NO,@"explicit_machine_authorization_invoked":@NO,
        @"deauthorization_invoked":@NO,@"security_upgrade_accepted":@NO,
        @"accessibility_trusted":AXIsProcessTrusted()?@YES:@NO
    } mutableCopy];
    // Navigation metadata is separate; account screens never become arbitrary log text.
    NSMutableDictionary *navigation=[@{@"accessibility_trusted":report[@"accessibility_trusted"]} mutableCopy];
    NSRunningApplication *application=NavigateToSignIn(navigation);
    NSMutableDictionary *navigationStatus=[NSMutableDictionary dictionary];
    for(NSString *key in @[@"status",@"dismiss_welcome",@"decline_optional_sheet",@"open_account_menu",@"open_signin_dialog",
                          @"post_event_access",@"not_now_hit_test_verified",@"not_now_coordinate_click_posted"])
        if(navigation[key])navigationStatus[key]=navigation[key];
    report[@"navigation"]=navigationStatus;
    if(application){
        AXUIElementRef app=AXUIElementCreateApplication(application.processIdentifier);
        AXUIElementSetMessagingTimeout(app,1.0);
        Screen(app,report,@"navigation");
        if([navigation[@"status"] isEqual:@"signin_menu_invoked"]){
            if(preflight){
                NSDictionary *form=FindForm(app,NO);
                report[@"email_form_ready"]=form?@YES:@NO;
                if(form && Fill(form,@"probe@example.invalid")){
                    id enabled=ReadAttribute((__bridge AXUIElementRef)form[@"submit"],kAXEnabledAttribute);
                    report[@"synthetic_email_fill_ready"]=[enabled isKindOfClass:NSNumber.class]&&[enabled boolValue]?@YES:@NO;
                    report[@"synthetic_email_cleared"]=Fill(form,@"")?@YES:@NO;
                    report[@"status"]=[report[@"synthetic_email_fill_ready"] boolValue] &&
                        [report[@"synthetic_email_cleared"] boolValue]?@"preflight_ready":@"preflight_failed";
                }else report[@"status"]=@"preflight_failed";
                Screen(app,report,@"preflight");
            }else Query(app,private,report);
        }
        CFRelease(app);[application terminate];
        Pump(1);
        if(!application.terminated)[application forceTerminate];
    }
    NSData *output=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingSortedKeys error:nil];
    if(!output)return 3;
    [NSFileHandle.fileHandleWithStandardOutput writeData:output];
    [NSFileHandle.fileHandleWithStandardOutput writeData:[@"\n" dataUsingEncoding:NSUTF8StringEncoding]];
    return 0;
}}
